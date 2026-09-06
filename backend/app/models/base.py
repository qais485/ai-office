import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import UUID

from app.database.session import Base


def utc_now() -> datetime:
    """Timezone-aware UTC now — never use naive datetime.utcnow()."""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """DateTime column that always works in UTC.

    The database stores naive UTC values (TIMESTAMP WITHOUT TIME ZONE).
    On load we attach UTC tzinfo so Pydantic/FastAPI serialize timestamps
    WITH an explicit offset (e.g. "2026-02-12T14:55:00+00:00"). Without
    this, `new Date(...)` in the browser parsed offset-less strings as
    LOCAL time, which skewed every relative timestamp by the viewer's UTC
    offset (e.g. "5 minutes ago" displayed as "4 hours ago" at UTC+4:30).
    """
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        # Normalize aware datetimes to naive UTC for storage.
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        # Values loaded from the DB are naive UTC — label them as UTC.
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class TimestampMixin:
    created_at = Column(UTCDateTime, default=utc_now, nullable=False)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=True)


class BaseModel(Base, TimestampMixin):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
