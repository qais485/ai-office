from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    agent_id: UUID
    assigned_by: Optional[UUID] = None
    assigned_to_agent_id: Optional[UUID] = None
    priority: str = "medium"
    task_type: str = "general"


class TaskCreate(TaskBase):
    input_json: Optional[dict] = None
    parent_task_id: Optional[UUID] = None
    tool_name: Optional[str] = None
    tool_action: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    result: Optional[str] = None
    priority: Optional[str] = None
    task_type: Optional[str] = None
    assigned_to_agent_id: Optional[UUID] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    output_json: Optional[dict] = None
    tool_name: Optional[str] = None
    tool_action: Optional[str] = None


class TaskResponse(TaskBase):
    id: UUID
    status: str
    result: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    input_json: Optional[dict] = None
    output_json: Optional[dict] = None
    parent_task_id: Optional[UUID] = None
    approval_id: Optional[UUID] = None
    tool_name: Optional[str] = None
    tool_action: Optional[str] = None
    agent_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
