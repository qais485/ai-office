"""Gmail Sync State model — tracks which Gmail messages have been processed.

Each row represents one Gmail account's sync state. Used for:
- Deduplication (prevent processing same email twice)
- Tracking last sync time
- Recording the last processed Gmail history ID for future delta syncs
"""
from sqlalchemy import Column, String, Boolean, Integer, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class GmailSyncState(BaseModel):
    """Tracks sync state for a connected Gmail account."""
    __tablename__ = "gmail_sync_states"

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

    # Gmail profile info
    gmail_address = Column(String(255), nullable=True)
    gmail_history_id = Column(String(100), nullable=True)
    messages_total = Column(Integer, nullable=True)

    # Sync control
    is_active = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(String, nullable=True)
    sync_error = Column(String(500), nullable=True)
    consecutive_errors = Column(Integer, default=0, nullable=True)

    # Processed message tracking
    processed_message_ids = Column(JSON, default=list, nullable=True)
    total_processed = Column(Integer, default=0, nullable=True)
