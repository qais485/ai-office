from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class ToolActionBase(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    risk_level: str = "low"
    requires_approval: bool = False
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    is_active: bool = True


class ToolActionCreate(ToolActionBase):
    tool_id: UUID


class ToolActionUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = None
    requires_approval: Optional[bool] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    is_active: Optional[bool] = None


class ToolActionResponse(ToolActionBase):
    id: UUID
    tool_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ToolPermissionBase(BaseModel):
    tool_id: UUID
    action_id: Optional[UUID] = None
    permission_id: UUID
    is_required: bool = True


class ToolPermissionCreate(ToolPermissionBase):
    pass


class ToolPermissionResponse(ToolPermissionBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ToolBase(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    category: str = "general"
    integration_id: Optional[UUID] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    risk_level: str = "low"
    requires_approval: bool = False
    is_active: bool = True
    version: str = "1.0.0"


class ToolCreate(ToolBase):
    pass


class ToolUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    integration_id: Optional[UUID] = None
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    risk_level: Optional[str] = None
    requires_approval: Optional[bool] = None
    is_active: Optional[bool] = None
    version: Optional[str] = None


class ToolResponse(ToolBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ToolWithActionsResponse(ToolResponse):
    actions: List[ToolActionResponse] = []
    permissions: List[ToolPermissionResponse] = []


class AgentToolAssignmentBase(BaseModel):
    agent_id: UUID
    tool_id: UUID
    is_enabled: bool = True
    config: Optional[dict] = None


class AgentToolAssignmentCreate(AgentToolAssignmentBase):
    pass


class AgentToolAssignmentResponse(AgentToolAssignmentBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
