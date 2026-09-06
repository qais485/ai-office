"""AI Virtual Office Platform — FastAPI application entry point.

IMPORTANT: setup_logging() MUST be called before importing any app modules
so that all subsequent `logging.getLogger(__name__)` calls use the
configured handlers from the start.
"""
import logging
import asyncio
import sys
import time

# ── Logging must be initialized FIRST ────────────────────────────────
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging(settings.ENVIRONMENT)

# ── Now safe to import everything else ────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.v1.router import api_router
from app.api.websocket import manager
from app.database.session import SessionLocal, check_db_health
from app.services.email_account_service import EmailAccountService
from app.services.seed_service import seed_all
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.http_logging import HTTPLoggingMiddleware
from app.events import register_handlers, set_connection_manager
from app.events.triggers import register_trigger_handlers
from app.events.bus import event_bus
from app.services.scheduler import scheduler

logger = logging.getLogger(__name__)


def _validate_startup():
    """Validate critical configuration before starting."""
    errors = []

    if settings.ENVIRONMENT == "production":
        if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key-change-in-production":
            errors.append("SECRET_KEY must be set in production")
        if not settings.ENCRYPTION_KEY:
            errors.append("ENCRYPTION_KEY must be set in production")
        if "localhost" in settings.DATABASE_URL:
            errors.append("DATABASE_URL must not point to localhost in production")

    if errors:
        for e in errors:
            logger.critical(f"STARTUP VALIDATION FAILED: {e}")
        sys.exit(1)

    logger.info(f"Startup validation passed (environment={settings.ENVIRONMENT})")


def _check_database():
    """Verify database is reachable."""
    health = check_db_health()
    if health["status"] != "healthy":
        logger.critical(f"Database is not healthy: {health}")
        if settings.ENVIRONMENT == "production":
            sys.exit(1)
        logger.warning("Continuing despite database issue (development mode)")
    else:
        logger.info(f"Database connected (pool: {health['pool']})")


def _run_migrations():
    """Run Alembic migrations automatically."""
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        if settings.ENVIRONMENT == "production":
            sys.exit(1)
        logger.warning("Continuing without migrations (development mode)")


def _create_tables():
    """Create any missing tables (development fallback when migrations are not run)."""
    try:
        from app.database.session import engine
        from app.models import base as _base  # noqa: ensure all models are imported
        # Import every model module so Base.metadata knows about all tables
        import app.models.agent
        import app.models.agent_trigger
        import app.models.trigger_execution
        import app.models.gmail_sync_state
        import app.models.gmail_execution
        import app.models.integration
        import app.models.integration_account
        import app.models.agent_integration
        import app.models.tool
        import app.models.tool_action
        import app.models.permission
        import app.models.agent_permission
        import app.models.agent_tool_assignment
        import app.models.room
        import app.models.approval
        import app.models.risk_rule
        import app.models.task
        import app.models.template
        import app.models.user
        import app.models.knowledge
        import app.models.notification
        import app.models.audit_log
        import app.models.email_account

        from app.models.base import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified (create_all)")
    except Exception as e:
        logger.error(f"Table creation failed: {e}", exc_info=True)
        if settings.ENVIRONMENT == "production":
            sys.exit(1)
        logger.warning("Continuing without table creation (development mode)")


def seed_new_data():
    """Seed templates, integrations, tools, permissions (idempotent)."""
    from app.database.retry import db_retry

    @db_retry(max_retries=2, base_delay=1.0)
    def _seed():
        db = SessionLocal()
        try:
            seed_all(db)
        except Exception as e:
            logger.error(f"Failed to seed new data: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    _seed()


async def poll_email_once():
    """Single email sync pass — called by the scheduler."""
    from app.database.retry import db_retry

    @db_retry(max_retries=2, base_delay=1.0)
    def _poll():
        db = SessionLocal()
        try:
            service = EmailAccountService(db)
            due_accounts = service.get_accounts_needing_sync()
            for account in due_accounts:
                try:
                    result = asyncio.run(service.sync_account(account.id))
                    if result.get("new_emails", 0) > 0:
                        logger.info(f"Synced {result['new_emails']} new emails from {account.email_address}")
                except Exception as e:
                    logger.error(f"Failed to sync {account.email_address}: {e}", exc_info=True)
        finally:
            db.close()

    try:
        await asyncio.to_thread(_poll)
    except Exception as e:
        logger.error(f"Email polling error after retries: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start = time.time()

    # ── Re-apply logging after uvicorn's dictConfig may have wiped it ─
    setup_logging(settings.ENVIRONMENT)

    # ── Startup ──────────────────────────────────────────────────────
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} ({settings.ENVIRONMENT})")
    _validate_startup()
    _check_database()
    _create_tables()
    seed_new_data()

    # Wire event system
    set_connection_manager(manager)
    register_handlers()
    register_trigger_handlers()
    await event_bus.start()
    await manager.start_heartbeat()
    logger.info("Event system initialized (event bus + handlers + heartbeat)")

    # ── Register scheduled jobs ──────────────────────────────────────
    # Email polling job
    scheduler.register_job(
        name="email_polling",
        func=poll_email_once,
        interval_seconds=settings.EMAIL_POLL_INTERVAL,
    )

    # Gmail API monitoring job
    from app.services.gmail_monitor_service import check_all_gmail_accounts
    scheduler.register_job(
        name="gmail_monitoring",
        func=check_all_gmail_accounts,
        interval_seconds=settings.GMAIL_POLL_INTERVAL,
    )

    # Gmail Push notification watch renewal job (if push is enabled)
    if getattr(settings, "GMAIL_PUSH_ENABLED", False):
        async def gmail_watch_renewal():
            """Renew Gmail watches that are expiring within 24 hours."""
            from app.database.retry import db_retry

            @db_retry(max_retries=2, base_delay=1.0)
            def _renew():
                db = SessionLocal()
                try:
                    from app.services.gmail_push_service import GmailPushService
                    push_service = GmailPushService(db)
                    push_service.setup_all_watches()
                finally:
                    db.close()

            try:
                await asyncio.to_thread(_renew)
            except Exception as e:
                logger.error(f"Gmail watch renewal error after retries: {e}", exc_info=True)

        scheduler.register_job(
            name="gmail_watch_renewal",
            func=gmail_watch_renewal,
            interval_seconds=getattr(settings, "GMAIL_WATCH_RENEWAL_INTERVAL", 21600),
        )
        logger.info("Gmail push notification watch renewal job registered")

    # Start scheduler
    await scheduler.start()
    logger.info(
        "Scheduler started",
        extra={
            "email_interval": settings.EMAIL_POLL_INTERVAL,
            "gmail_interval": settings.GMAIL_POLL_INTERVAL,
        },
    )

    # Start agent runtime (activates existing agents + scheduled trigger worker)
    from app.services.agent_runtime import agent_runtime
    await agent_runtime.start()
    logger.info("Agent runtime started")

    logger.info(f"Startup complete in {time.time() - start:.1f}s")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down...")

    # Stop agent runtime
    from app.services.agent_runtime import agent_runtime
    await agent_runtime.stop()
    logger.info("Agent runtime stopped")

    # Stop scheduler
    await scheduler.stop()
    logger.info("Scheduler stopped")

    await manager.stop_heartbeat()
    logger.info("WebSocket heartbeat stopped")

    await event_bus.stop()
    logger.info("Event bus stopped")

    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI Virtual Office Platform API",
    lifespan=lifespan,
)

# ── Middleware (order matters: last added = first executed) ───────────
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
app.add_middleware(HTTPLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "AI Virtual Office Platform API",
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    from app.database.session import check_db_health
    db_health = check_db_health()
    return {
        "status": "healthy" if db_health["status"] == "healthy" else "degraded",
        "database": db_health,
    }


