from sqlalchemy import Column, String, Enum, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.models.base import BaseModel


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskType(str, enum.Enum):
    TOOL_EXECUTION = "tool_execution"
    AGENT_COLLABORATION = "agent_collaboration"
    APPROVAL_REQUIRED = "approval_required"
    GENERAL = "general"


class Task(BaseModel):
    __tablename__ = "tasks"

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus, values_callable=lambda obj: [e.value for e in obj]), default=TaskStatus.PENDING, nullable=False)
    task_type = Column(Enum(TaskType, values_callable=lambda obj: [e.value for e in obj]), default=TaskType.GENERAL, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_to_agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=True)
    result = Column(Text, nullable=True)
    priority = Column(Enum(TaskPriority, values_callable=lambda obj: [e.value for e in obj]), default=TaskPriority.MEDIUM, nullable=False)

    started_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    input_json = Column(JSON, nullable=True)
    output_json = Column(JSON, nullable=True)
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    approval_id = Column(UUID(as_uuid=True), ForeignKey("approvals.id"), nullable=True)
    tool_name = Column(String, nullable=True)
    tool_action = Column(String, nullable=True)
