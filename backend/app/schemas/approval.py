from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class ApprovalBase(BaseModel):
    agent_id: UUID
    task_id: Optional[UUID] = None
    action: str
    tool_id: Optional[UUID] = None
    parameters: Optional[dict] = None
    reason: Optional[str] = None
    risk_level: str = "low"


class ApprovalCreate(ApprovalBase):
    pass


class ApprovalUpdate(BaseModel):
    status: Optional[str] = None
    decided_at: Optional[str] = None
    decided_by: Optional[UUID] = None
    decision_notes: Optional[str] = None


class ApprovalResponse(ApprovalBase):
    id: UUID
    status: str
    requested_at: Optional[str] = None
    decided_at: Optional[str] = None
    decided_by: Optional[UUID] = None
    decision_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
