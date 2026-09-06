from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class AuditLogBase(BaseModel):
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    user_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None


class AuditLogResponse(AuditLogBase):
    id: UUID
    user_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True
