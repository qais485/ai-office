"""HTTP request/response logging middleware.

Logs every incoming request and outgoing response with timing,
status codes, and client information. Skips health checks and
docs endpoints in normal operation to reduce noise.
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.http")

# Paths to skip logging (health checks, docs, OpenAPI)
SKIP_LOG_PATHS = frozenset({
    "/health",
    "/health/ready",
    "/health/info",
    "/docs",
    "/redoc",
    "/openapi.json",
})


class HTTPLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, duration, and client IP for every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip noisy health check / docs paths
        skip = path in SKIP_LOG_PATHS or path.startswith("/docs")
        if skip:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        method = request.method
        start = time.perf_counter()

        logger.info(f"--> {method} {path} from {client_ip}")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                f"<-- {method} {path} ERROR after {duration_ms:.0f}ms",
                exc_info=True,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        status = response.status_code
        request_id = getattr(request.state, "request_id", "")

        log_msg = f"<-- {method} {path} {status} {duration_ms:.0f}ms"
        if request_id:
            log_msg += f" [{request_id[:8]}]"

        if status >= 500:
            logger.error(log_msg)
        elif status >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
