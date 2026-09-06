from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    risk_level: str = "low"
    default_status: str = "allowed"  # allowed, approval_required, denied
    default_approval_required: bool = False  # Kept for backwards compatibility
    is_active: bool = True


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    risk_level: Optional[str] = None
    default_status: Optional[str] = None
    default_approval_required: Optional[bool] = None
    is_active: Optional[bool] = None


class PermissionResponse(PermissionBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentPermissionBase(BaseModel):
    permission_id: UUID
    access_level: str = "allowed"  # allowed, approval_required, denied
    conditions: Optional[dict] = None
    granted_by: Optional[str] = None
    notes: Optional[str] = None


class AgentPermissionCreate(AgentPermissionBase):
    pass


class AgentPermissionUpdate(BaseModel):
    access_level: Optional[str] = None
    conditions: Optional[dict] = None
    notes: Optional[str] = None


class AgentPermissionResponse(AgentPermissionBase):
    id: UUID
    agent_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentPermissionWithDetails(AgentPermissionResponse):
    permission_name: str
    permission_description: Optional[str] = None
    permission_category: str
    permission_risk_level: str


class PermissionCheckRequest(BaseModel):
    agent_id: UUID
    permission_name: str


class PermissionCheckResponse(BaseModel):
    has_permission: bool
    access_level: str
    message: str
    requires_approval: bool = False
