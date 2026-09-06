"""Database retry utilities for transient Neon PostgreSQL errors.

Provides safe retry behavior for operations that may fail due to:
- Stale connections (SSL EOF)
- Neon pooler connection resets
- Network blips
- Temporary connection exhaustion

IMPORTANT: Only use this for idempotent operations (reads, upserts, or
operations that are safe to retry). Never retry non-idempotent writes
blindly — the caller must ensure retry safety.
"""
import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Optional, Tuple

from sqlalchemy.exc import OperationalError, DisconnectionError, IntegrityError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 0.5  # seconds
DEFAULT_MAX_DELAY = 5.0   # seconds

# Errors that are safe to retry (transient connection issues)
RETRYABLE_ERRORS = (OperationalError, DisconnectionError)

# Error messages that indicate transient issues
RETRYABLE_MESSAGES = (
    "SSL SYSCALL error: EOF detected",
    "server closed the connection unexpectedly",
    "connection already closed",
    "remaining connection slots",
    "could not connect to server",
    "connection timed out",
    "no connection to the server",
    "the connection was closed",
)


def _is_retryable_error(exc: Exception) -> bool:
    """Determine if an exception is transient and safe to retry."""
    if not isinstance(exc, RETRYABLE_ERRORS):
        return False
    error_msg = str(exc).lower()
    return any(msg in error_msg for msg in RETRYABLE_MESSAGES)


def db_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """Decorator that retries a function on transient database errors.

    Usage::

        @db_retry(max_retries=3)
        def sync_account(account_id):
            ...

        @db_retry(max_retries=2)
        async def check_gmail():
            ...

    The decorated function must accept a `db` keyword argument or be called
    within a context where database sessions are managed externally.

    Args:
        max_retries: Maximum number of retry attempts (0 = no retries).
        base_delay: Base delay in seconds (doubled each retry).
        max_delay: Maximum delay between retries.
        on_retry: Optional callback invoked on each retry with (exception, attempt).
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RETRYABLE_ERRORS as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        error_msg = str(e)

                        # Determine specific log level based on error type
                        if "SSL SYSCALL" in error_msg or "EOF detected" in error_msg:
                            log_fn = logger.warning
                            context = "Neon connection lost (SSL EOF)"
                        elif "remaining connection slots" in error_msg:
                            log_fn = logger.warning
                            context = "Connection limit reached"
                        elif "connection timed out" in error_msg:
                            log_fn = logger.warning
                            context = "Connection timed out"
                        else:
                            log_fn = logger.info
                            context = "Transient database error"

                        log_fn(
                            f"{context}, retrying in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{max_retries})",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "delay_seconds": delay,
                                "error": error_msg[:200],
                            },
                        )

                        if on_retry:
                            on_retry(e, attempt + 1)

                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Database retry exhausted for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "attempts": max_retries + 1,
                                "error": str(e)[:200],
                            },
                        )
            raise last_exception
        return wrapper
    return decorator


class RetryableSession:
    """Wrapper around a SQLAlchemy session that retries transient errors.

    Use this for background tasks where you want automatic retry behavior
    on connection failures. Do NOT use this for API endpoints where the
    FastAPI dependency injection manages the session lifecycle.

    Usage::

        db = SessionLocal()
        try:
            with RetryableSession(db) as session:
                result = session.query(User).all()
        finally:
            db.close()
    """

    def __init__(self, db, max_retries: int = 2, base_delay: float = 0.5):
        self.db = db
        self.max_retries = max_retries
        self.base_delay = base_delay

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and isinstance(exc_val, RETRYABLE_ERRORS):
            if _is_retryable_error(exc_val):
                try:
                    self.db.rollback()
                except Exception:
                    pass
        return False  # Don't suppress exceptions

    def execute_with_retry(self, operation: Callable, *args, **kwargs):
        """Execute a database operation with retry on transient errors.

        Args:
            operation: A callable that takes the session as its first argument.
            *args, **kwargs: Additional arguments passed to the operation.

        Returns:
            The result of the operation.

        Raises:
            The last exception if all retries fail.
        """
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                return operation(self.db, *args, **kwargs)
            except RETRYABLE_ERRORS as e:
                last_exception = e
                if attempt < self.max_retries and _is_retryable_error(e):
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        f"Transient DB error in operation, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})",
                        extra={
                            "attempt": attempt + 1,
                            "error": str(e)[:200],
                        },
                    )
                    time.sleep(delay)
                    # Rollback the failed transaction before retry
                    try:
                        self.db.rollback()
                    except Exception:
                        pass
                else:
                    raise
        raise last_exception
