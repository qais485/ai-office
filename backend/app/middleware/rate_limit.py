import time
import logging
from collections import defaultdict
from typing import Dict, List, Set
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

# Paths that should not be rate-limited (health checks, docs)
EXEMPT_PATHS: Set[str] = {
    "/health",
    "/health/ready",
    "/health/info",
    "/api/v1/health/",
    "/api/v1/health/info",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup: float = time.time()
        self._cleanup_interval: float = 60.0

    def get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_stale_entries(self) -> None:
        """Periodically remove stale entries to prevent memory leak."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        window_start = now - 60
        stale_keys = [
            ip for ip, times in self.requests.items()
            if not times or times[-1] < window_start
        ]
        for ip in stale_keys:
            del self.requests[ip]
        if stale_keys:
            logger.debug(f"Rate limiter cleaned up {len(stale_keys)} stale entries")

    async def dispatch(self, request: Request, call_next):
        # Exempt health/auth/docs paths
        if request.url.path in EXEMPT_PATHS or request.url.path.startswith("/docs"):
            return await call_next(request)

        client_ip = self.get_client_ip(request)
        now = time.time()
        window_start = now - 60

        self._cleanup_stale_entries()

        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip] if req_time > window_start
        ]

        if len(self.requests[client_ip]) >= self.requests_per_minute:
            retry_after = int(self.requests[client_ip][0] + 60 - now) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(max(1, retry_after))}
            )

        self.requests[client_ip].append(now)

        response = await call_next(request)
        remaining = self.requests_per_minute - len(self.requests[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(now + 60))

        return response
