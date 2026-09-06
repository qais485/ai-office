from sqlalchemy import Column, String, Enum, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.models.base import BaseModel


class EmailStatus(str, enum.Enum):
    NEW = "new"
    PROCESSING = "processing"
    REPLIED = "replied"
    ESCALATED = "escalated"
    FAILED = "failed"


class EmailMessage(BaseModel):
    __tablename__ = "email_messages"

    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(Enum(EmailStatus, values_callable=lambda obj: [e.value for e in obj]), default=EmailStatus.NEW, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=True)
    conversation_id = Column(String, nullable=True)
    draft_response = Column(Text, nullable=True)
    category = Column(String, nullable=True, default="general")
    account_id = Column(UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=True)

    __table_args__ = (
        # Anti-duplicate guard: one email row per (account, source message id).
        # conversation_id holds the Gmail message id / IMAP uid of the ORIGINAL
        # incoming message. Nullable-safe: PostgreSQL UNIQUE ignores NULLs.
        Index(
            "uq_email_messages_account_conversation",
            account_id,
            conversation_id,
            unique=True,
        ),
        # Reply-guard uniqueness: only ONE reply-guard row per source message,
        # regardless of account_id being NULL (partial index keeps the general
        # table schema untouched).
        Index(
            "uq_email_reply_guard_conversation",
            conversation_id,
            unique=True,
            postgresql_where=Text("category = 'reply_guard'"),
            sqlite_where=Text("category = 'reply_guard'"),
        ),
    )
