"""GmailExecution — durable idempotency record for Gmail-triggered agent work.

Each row represents a single attempt to process a specific Gmail message for
a specific agent.  A unique constraint on
    (integration_account_id, gmail_message_id, agent_id, event_type)
prevents concurrent duplicate processing at the database level.

Statuses:
    pending     — row created, processing not yet started
    processing  — a worker has claimed this record
    completed   — processing finished successfully
    failed      — processing finished with an error
    retrying    — previous attempt failed, eligible for retry
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean, Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class GmailExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class GmailExecution(BaseModel):
    """One record per (account, message, agent, event_type) combination."""

    __tablename__ = "gmail_executions"

    # ── Identity ──────────────────────────────────────────────────────
    integration_account_id = Column(
        UUID(as_uuid=True), nullable=False, index=True,
        comment="Which Gmail account received the message",
    )
    gmail_message_id = Column(
        String(255), nullable=False, index=True,
        comment="Gmail API message ID",
    )
    agent_id = Column(
        UUID(as_uuid=True), nullable=False, index=True,
        comment="Which agent should process this message",
    )
    event_type = Column(
        String(100), nullable=False, default="email_received",
        comment="Event classifier (e.g. email_received, email_replied)",
    )

    # ── Status ────────────────────────────────────────────────────────
    status = Column(
        String(20), nullable=False, default=GmailExecutionStatus.PENDING.value,
        comment="Current processing status",
    )
    idempotency_key = Column(
        String(512), nullable=False, unique=True,
        comment="Deterministic hash: account_id + message_id + agent_id + event_type",
    )

    # ── Retry tracking ────────────────────────────────────────────────
    attempt = Column(Integer, nullable=False, default=1, comment="Current attempt number")
    max_retries = Column(Integer, nullable=False, default=3, comment="Maximum retry attempts")
    next_retry_at = Column(DateTime, nullable=True, comment="Earliest time the next retry may run")

    # ── Result ────────────────────────────────────────────────────────
    trigger_id = Column(UUID(as_uuid=True), nullable=True, comment="FK to agent_triggers if a trigger was created")
    error_message = Column(Text, nullable=True, comment="Last error message (truncated to 2000 chars)")
    processed_at = Column(DateTime, nullable=True, comment="Timestamp of successful completion")

    # ── Duplicate attempt tracking ────────────────────────────────────
    duplicate_attempts = Column(Integer, nullable=False, default=0, comment="How many times a duplicate was rejected")

    # ── Unique constraint ─────────────────────────────────────────────
    __table_args__ = (
        Index(
            "ix_gmail_executions_identity",
            "integration_account_id",
            "gmail_message_id",
            "agent_id",
            "event_type",
            unique=True,
        ),
    )

    # ── Helpers ───────────────────────────────────────────────────────
    @property
    def is_terminal(self) -> bool:
        """True when the record will never be retried."""
        return self.status in (
            GmailExecutionStatus.COMPLETED.value,
        )

    @property
    def is_retry_eligible(self) -> bool:
        """True when the record may be retried."""
        if self.status not in (
            GmailExecutionStatus.FAILED.value,
            GmailExecutionStatus.RETRYING.value,
        ):
            return False
        if self.attempt >= self.max_retries:
            return False
        if self.next_retry_at and self.next_retry_at > datetime.now(timezone.utc):
            return False
        return True
