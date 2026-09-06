from sqlalchemy import Column, String, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.models.base import BaseModel


class EmailAccount(BaseModel):
    __tablename__ = "email_accounts"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    email_address = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    imap_host = Column(String, nullable=False)
    imap_port = Column(Integer, nullable=False, default=993)
    imap_username = Column(String, nullable=False)
    imap_password = Column(String, nullable=False)
    imap_use_ssl = Column(Boolean, nullable=False, default=True)
    smtp_host = Column(String, nullable=False)
    smtp_port = Column(Integer, nullable=False, default=587)
    smtp_username = Column(String, nullable=False)
    smtp_password = Column(String, nullable=False)
    smtp_use_ssl = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_sync_at = Column(String, nullable=True)
    sync_error = Column(String, nullable=True)
    sync_frequency_minutes = Column(Integer, nullable=False, default=5)
