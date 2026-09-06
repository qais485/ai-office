from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class NotificationBase(BaseModel):
    type: str
    title: str
    message: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[UUID] = None
    priority: str = "low"


class NotificationCreate(NotificationBase):
    user_id: UUID


class NotificationResponse(NotificationBase):
    id: UUID
    user_id: UUID
    is_read: bool
    is_archived: bool = False
    is_resolved: bool = False
    created_at: datetime

    class Config:
        from_attributes = True
