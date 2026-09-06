from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class ActivityBase(BaseModel):
    agent_id: UUID
    activity_type: str
    description: Optional[str] = None
    metadata_json: Optional[dict] = None
    task_id: Optional[UUID] = None
    tool_name: Optional[str] = None
    status: Optional[str] = None


class ActivityCreate(ActivityBase):
    pass


class ActivityResponse(ActivityBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
