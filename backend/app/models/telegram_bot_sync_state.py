"""Telegram Bot Sync State model — tracks which Bot updates have been processed.

Each row represents one connected Telegram *Bot* integration account. Mirrors
``TelegramSyncState`` / ``GmailSyncState``: durable getUpdates offset so the
customer-chat loop neither replays old updates nor loses new ones.
"""
from sqlalchemy import Column, String, Boolean, BigInteger, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class TelegramBotSyncState(BaseModel):
    """Tracks getUpdates state for a connected Telegram Bot account."""
    __tablename__ = "telegram_bot_sync_states"

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

    # Bot profile info
    bot_username = Column(String(100), nullable=True)

    # Sync control
    is_active = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(String, nullable=True)
    sync_error = Column(String(500), nullable=True)
    consecutive_errors = Column(Integer, default=0, nullable=True)

    # getUpdates offset: only updates ABOVE this id are new (acked processing)
    last_update_id = Column(BigInteger, nullable=True)
    total_processed = Column(Integer, default=0, nullable=True)
