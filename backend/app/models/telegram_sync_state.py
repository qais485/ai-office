"""Telegram Sync State model — tracks which Telegram (MTProto) messages have
been processed.

Each row represents one connected Telegram *Account* integration's sync state.
Mirrors ``GmailSyncState``: used for
- Deduplication (never process/fire the same incoming message twice)
- Tracking last sync time
- Baseline watermarking (first poll only records, never fires agents)
"""
from sqlalchemy import Column, String, Boolean, Integer, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class TelegramSyncState(BaseModel):
    """Tracks sync state for a connected Telegram Account (MTProto)."""
    __tablename__ = "telegram_sync_states"

    integration_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integration_accounts.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Telegram profile info
    telegram_username = Column(String(100), nullable=True)

    # Sync control
    is_active = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(String, nullable=True)
    sync_error = Column(String(500), nullable=True)
    consecutive_errors = Column(Integer, default=0, nullable=True)

    # Processed message tracking
    # Watermark per dialog: {dialog_id_str: last_seen_message_id_int}
    last_seen_message_ids = Column(JSON, default=dict, nullable=True)
    # Restart safety net: recent "dialog_id:message_id" markers (capped)
    processed_message_ids = Column(JSON, default=list, nullable=True)
    total_processed = Column(Integer, default=0, nullable=True)
