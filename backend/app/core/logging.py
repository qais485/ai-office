import logging
import logging.config
import sys
import json
from datetime import datetime, timezone
from typing import Any


LOG_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log_entry["stack_info"] = record.stack_info

        return json.dumps(log_entry, default=str)


class DevFormatter(logging.Formatter):
    """Human-readable formatter for development with color coding."""

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[1;31m",# Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        request_id = getattr(record, "request_id", "")
        color = self.LEVEL_COLORS.get(record.levelname, "")

        prefix = f"{color}[{timestamp}] [{record.levelname:8s}]{self.RESET}"
        if request_id:
            prefix += f" [{request_id[:8]}]"
        prefix += f" {record.name}"

        msg = record.getMessage()
        if record.exc_info and record.exc_info[0]:
            msg += "\n" + self.formatException(record.exc_info)

        return f"{prefix}: {msg}"


def _make_handler(fmt: logging.Formatter, level: int) -> logging.StreamHandler:
    """Create a fresh stdout StreamHandler."""
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(level)
    h.setFormatter(fmt)
    return h


def setup_logging(
    environment: str = "development",
    log_level: str = "info",
) -> None:
    """Configure application-wide logging.

    Configures loggers **manually** instead of using ``dictConfig``.
    ``dictConfig`` interacts badly with uvicorn's own ``dictConfig``
    call (it resets child loggers and sets ``disabled=True`` on loggers
    that exist outside the config dict).

    Manual configuration avoids these hidden side-effects and is safe
    to call multiple times (import-time + lifespan).

    Args:
        environment: "development" or "production"
        log_level: Override log level (debug, info, warning, error, critical)
    """
    level = LOG_LEVEL_MAP.get(log_level.lower(), logging.INFO)

    if environment == "development" and log_level == "info":
        level = logging.DEBUG

    fmt = JSONFormatter() if environment == "production" else DevFormatter()

    root = logging.getLogger()

    # ── Clear all existing handlers to prevent duplicates ───────────
    for name in list(logging.Logger.manager.loggerDict.keys()):
        logging.getLogger(name).handlers.clear()
    root.handlers.clear()

    # ── Root logger ────────────────────────────────────────────────
    root.setLevel(logging.DEBUG)
    root.addHandler(_make_handler(fmt, level))

    # ── App loggers: own handler, propagate=False ───────────────────
    # Uses setLevel() (not attribute assignment) to invalidate the
    # isEnabledFor cache that dictConfig leaves stale.
    for name in ("app", "app.http"):
        lgr = logging.getLogger(name)
        lgr.setLevel(logging.DEBUG)
        lgr.propagate = False
        lgr.addHandler(_make_handler(fmt, level))

    # ── Uvicorn ────────────────────────────────────────────────────
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    # ── Libraries: silenced ────────────────────────────────────────
    for name in (
        "starlette", "fastapi",
        "sqlalchemy", "sqlalchemy.engine", "sqlalchemy.pool", "sqlalchemy.orm",
        "httpx", "httpcore",
        "google", "google.auth", "google.oauth2",
        "websockets",
        # The OpenAI client logs every full request/response payload at DEBUG
        # (entire LLM prompts). That is log spam, not signal.
        "openai", "openai._base_client",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger("alembic").setLevel(logging.INFO)
    logging.getLogger("alembic.runtime.migration").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging initialized: environment={environment}, "
        f"level={logging.getLevelName(level)}"
    )

