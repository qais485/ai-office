import time
from fastapi import APIRouter
from app.core.config import settings
from app.database.session import check_db_health

router = APIRouter()

_start_time = time.time()


@router.get("/")
async def health_check():
    """Liveness check — is the process alive?"""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check():
    """Readiness check — can the service handle requests?"""
    checks = {}
    all_healthy = True

    # Database check
    db_health = check_db_health()
    checks["database"] = db_health
    if db_health["status"] != "healthy":
        all_healthy = False

    # Uptime
    checks["uptime_seconds"] = round(time.time() - _start_time, 1)

    # Event bus check
    try:
        from app.events.bus import event_bus
        checks["event_bus"] = {"status": "running" if event_bus._running else "stopped"}
        if not event_bus._running:
            all_healthy = False
    except Exception as e:
        checks["event_bus"] = {"status": "error", "error": str(e)}
        all_healthy = False

    # WebSocket manager check
    try:
        from app.api.websocket import manager
        checks["websocket"] = {
            "status": "healthy",
            "connections": manager.connection_count,
        }
    except Exception as e:
        checks["websocket"] = {"status": "error", "error": str(e)}

    status_code = 200 if all_healthy else 503
    return {"status": "healthy" if all_healthy else "degraded", "checks": checks}


@router.get("/info")
async def health_info():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "operational",
    }
