from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class AgentTemplateBase(BaseModel):
    name: str
    role: str
    description: Optional[str] = None
    default_goals: Optional[List[str]] = None
    default_rules: Optional[List[str]] = None
    default_permissions: Optional[List[str]] = None
    default_tools: Optional[List[str]] = None
    default_knowledge: Optional[List[str]] = None
    icon_url: Optional[str] = None
    is_active: bool = True


class AgentTemplateCreate(AgentTemplateBase):
    pass


class AgentTemplateUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    default_goals: Optional[List[str]] = None
    default_rules: Optional[List[str]] = None
    default_permissions: Optional[List[str]] = None
    default_tools: Optional[List[str]] = None
    default_knowledge: Optional[List[str]] = None
    icon_url: Optional[str] = None
    is_active: Optional[bool] = None


class AgentTemplateResponse(AgentTemplateBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
