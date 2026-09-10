"""Discord Bot Sync State model — tracks which channel messages were processed.

Each row represents one connected Discord *Bot* integration account. Mirrors
``TelegramBotSyncState``: a durable per-channel message-id watermark so the
customer-chat loop neither replays old messages nor loses new ones.

Discord has no getUpdates-style offset, so the watermark is the highest
message id (snowflake) acknowledged per channel, stored as a JSON mapping
``{channel_id: last_message_id}``.
"""
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class DiscordBotSyncState(BaseModel):
    """Tracks inbound message state for a connected Discord Bot account."""
    __tablename__ = "discord_bot_sync_states"

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

    # Durable watermark: {channel_id: last_acknowledged_message_id}
    channel_offsets = Column(JSON, nullable=True)
    total_processed = Column(Integer, default=0, nullable=True)
