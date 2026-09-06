from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class EmailAccountBase(BaseModel):
    email_address: str
    display_name: Optional[str] = None
    imap_host: str
    imap_port: int = 993
    imap_username: str
    imap_password: str
    imap_use_ssl: bool = True
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    smtp_use_ssl: bool = True
    sync_frequency_minutes: int = 5


class EmailAccountCreate(EmailAccountBase):
    pass


class EmailAccountUpdate(BaseModel):
    email_address: Optional[str] = None
    display_name: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None
    imap_use_ssl: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_ssl: Optional[bool] = None
    is_active: Optional[bool] = None
    sync_frequency_minutes: Optional[int] = None


class EmailAccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    email_address: str
    display_name: Optional[str] = None
    imap_host: str
    imap_port: int
    imap_username: str
    imap_use_ssl: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_use_ssl: bool
    is_active: bool
    last_sync_at: Optional[str] = None
    sync_error: Optional[str] = None
    sync_frequency_minutes: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_model(cls, model):
        return cls(
            id=model.id,
            user_id=model.user_id,
            email_address=model.email_address,
            display_name=model.display_name,
            imap_host=model.imap_host,
            imap_port=model.imap_port,
            imap_username=model.imap_username,
            imap_use_ssl=model.imap_use_ssl,
            smtp_host=model.smtp_host,
            smtp_port=model.smtp_port,
            smtp_username=model.smtp_username,
            smtp_use_ssl=model.smtp_use_ssl,
            is_active=model.is_active,
            last_sync_at=model.last_sync_at,
            sync_error=model.sync_error,
            sync_frequency_minutes=model.sync_frequency_minutes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
