from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class AgentBase(BaseModel):
    name: str
    role: str
    description: Optional[str] = None
    status: str = "inactive"
    room_id: Optional[UUID] = None
    goals: Optional[str] = None
    rules: Optional[str] = None
    permissions: Optional[str] = None
    tools: Optional[str] = None
    memory_settings: Optional[str] = None


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    room_id: Optional[UUID] = None
    goals: Optional[str] = None
    rules: Optional[str] = None
    permissions: Optional[str] = None
    tools: Optional[str] = None
    memory_settings: Optional[str] = None


class AgentResponse(AgentBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    template_id: Optional[UUID] = None
    lifecycle_status: Optional[str] = None
    hired_at: Optional[str] = None
    last_active_at: Optional[str] = None
    paused_at: Optional[str] = None
    disabled_at: Optional[str] = None
    disabled_reason: Optional[str] = None
    last_error: Optional[str] = None
    archived_at: Optional[str] = None

    class Config:
        from_attributes = True
