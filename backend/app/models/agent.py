from sqlalchemy import Column, String, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.models.base import BaseModel


class AgentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUSY = "busy"


class LifecycleStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class AIAgent(BaseModel):
    __tablename__ = "ai_agents"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(Enum(AgentStatus, values_callable=lambda obj: [e.value for e in obj]), default=AgentStatus.INACTIVE, nullable=False)
    room_id = Column(UUID(as_uuid=True), ForeignKey("office_rooms.id"), nullable=True)
    goals = Column(String, nullable=True)
    rules = Column(String, nullable=True)
    permissions = Column(String, nullable=True)
    tools = Column(String, nullable=True)
    memory_settings = Column(String, nullable=True)
    
    template_id = Column(UUID(as_uuid=True), ForeignKey("agent_templates.id"), nullable=True)
    lifecycle_status = Column(Enum(LifecycleStatus, values_callable=lambda obj: [e.value for e in obj]), default=LifecycleStatus.DRAFT, nullable=False)
    hired_at = Column(String, nullable=True)
    last_active_at = Column(String, nullable=True)
    paused_at = Column(String, nullable=True)
    disabled_at = Column(String, nullable=True)
    disabled_reason = Column(Text, nullable=True)
    last_error = Column(Text, nullable=True)
    archived_at = Column(String, nullable=True)
