import logging
import time
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, DisconnectionError

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine configuration — tuned for Neon PostgreSQL pooler
# ---------------------------------------------------------------------------

def _create_engine():
    """Create engine with Neon-compatible settings.

    Key decisions:
    - pool_size=5: Neon free tier allows ~100 connections total. With multiple
      workers, 5 per worker is safer than 10.
    - pool_recycle=300: Neon's pooler idle timeout is typically 5 minutes.
      Recycling at 300s prevents stale connections.
    - pool_pre_ping=True: Detects dead connections before checkout.
    - connect_args: Explicit SSL configuration for Neon.
    """
    url = settings.DATABASE_URL

    # Neon pooler needs explicit SSL args in connect_args
    connect_args = {}
    if "neon.tech" in url:
        connect_args = {
            "sslmode": "require",
            "connect_timeout": 10,
        }

    engine = create_engine(
        url,
        poolclass=QueuePool,
        pool_size=getattr(settings, "DATABASE_POOL_SIZE", 15),
        max_overflow=getattr(settings, "DATABASE_MAX_OVERFLOW", 25),
        pool_timeout=getattr(settings, "DATABASE_POOL_TIMEOUT", 30),
        pool_recycle=getattr(settings, "DATABASE_POOL_RECYCLE", 300),
        pool_pre_ping=True,
        echo=False,
        connect_args=connect_args,
    )

    return engine


engine = _create_engine()


# ---------------------------------------------------------------------------
# Pool event listeners — structured logging for connection lifecycle
# ---------------------------------------------------------------------------

@event.listens_for(engine, "connect")
def _on_connect(dbapi_connection, connection_record):
    """Log when a new raw DBAPI connection is created."""
    logger.debug("Database connection created", extra={"pool_status": _pool_status(engine)})


@event.listens_for(engine, "checkout")
def _on_checkout(dbapi_connection, connection_record, connection_proxy):
    """Validate connection on checkout and log pool pressure."""
    connection_record.info["checkout_time"] = time.monotonic()
    # Only meaningful when the pool is actually saturated: capacity is
    # pool_size + max_overflow, and overflow() returns a NEGATIVE number
    # when there is spare capacity. Divide by the real capacity only when
    # the pool is maxed out, otherwise stay quiet — previously every normal
    # checkout logged "under pressure" noise (overflow: -14 → denominator 1).
    pool = engine.pool
    maxed_out = pool.overflow() >= 0
    if maxed_out:
        checked_out = pool.checkedout()
        capacity = pool.size() + pool.overflow()
        if capacity > 0 and checked_out / capacity > 0.8:
            logger.warning(
                "Database pool under pressure",
                extra={
                    "checked_out": checked_out,
                    "pool_size": pool.size(),
                    "overflow": pool.overflow(),
                    "checked_in": pool.checkedin(),
                },
            )


@event.listens_for(engine, "checkin")
def _on_checkin(dbapi_connection, connection_record):
    """Log connection checkin and track checkout duration."""
    checkout_time = connection_record.info.pop("checkout_time", None)
    if checkout_time:
        duration_ms = (time.monotonic() - checkout_time) * 1000
        if duration_ms > 5000:  # Log slow checkouts (>5s)
            logger.warning(
                "Slow database checkout detected",
                extra={"duration_ms": round(duration_ms, 1)},
            )


def _pool_status(eng):
    """Return pool status as a dict for structured logging."""
    pool = eng.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    }


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency — with rollback safety and structured error handling
# ---------------------------------------------------------------------------

def get_db():
    """FastAPI dependency that yields a database session.

    Guarantees:
    - Session is always closed (via finally).
    - Uncommitted work is rolled back on error.
    - Database errors are logged with context.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # Rollback uncommitted work on any error
        try:
            db.rollback()
        except Exception as rollback_err:
            logger.error(
                "Failed to rollback database session",
                extra={"rollback_error": str(rollback_err)},
            )
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health check — validates actual connectivity, not just pool state
# ---------------------------------------------------------------------------

def check_db_health() -> dict:
    """Verify database connectivity and return health status.

    Tests a real query (not just pool ping) to detect:
    - SSL connection failures
    - Neon pooler connection limits
    - Authentication issues
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        pool = engine.pool
        status = {
            "status": "healthy",
            "pool": _pool_status(engine),
        }
        logger.debug("Database health check passed", extra=status)
        return status
    except OperationalError as e:
        error_msg = str(e)
        # Log specific Neon-related errors with context
        if "SSL SYSCALL" in error_msg or "EOF detected" in error_msg:
            logger.error(
                "Database health check failed: Neon connection lost (SSL EOF). "
                "This usually means the Neon pooler closed the connection. "
                "Check Neon dashboard for connection limits or pauses.",
                extra={"error": error_msg, "pool": _pool_status(engine)},
            )
        elif "remaining connection slots" in error_msg:
            logger.error(
                "Database health check failed: Connection limit reached. "
                "Reduce pool_size or max_overflow, or upgrade Neon plan.",
                extra={"error": error_msg, "pool": _pool_status(engine)},
            )
        else:
            logger.error(
                "Database health check failed: OperationalError",
                extra={"error": error_msg, "pool": _pool_status(engine)},
            )
        return {"status": "unhealthy", "error": error_msg}
    except Exception as e:
        logger.error(
            "Database health check failed: unexpected error",
            extra={"error": str(e), "pool": _pool_status(engine)},
        )
        return {"status": "unhealthy", "error": str(e)}
