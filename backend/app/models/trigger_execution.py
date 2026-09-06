"""Trigger Execution model — records every trigger execution attempt.

Each execution gets a unique execution_id for tracing. Records:
- What trigger was fired
- What the agent decided to do
- What tools were executed
- Success/failure status
- Timing and error details
"""
import enum
from sqlalchemy import Column, String, Enum, ForeignKey, Text, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class ExecutionStatus(str, enum.Enum):
    STARTED = "started"
    REASONING = "reasoning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TriggerExecution(BaseModel):
    """A single execution record for a trigger."""
    __tablename__ = "trigger_executions"

    trigger_id = Column(UUID(as_uuid=True), ForeignKey("agent_triggers.id"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False, index=True)

    status = Column(Enum(ExecutionStatus, values_callable=lambda obj: [e.value for e in obj]), default=ExecutionStatus.STARTED, nullable=False)

    # What the agent decided
    llm_reasoning = Column(Text, nullable=True)
    selected_tool = Column(String(100), nullable=True)
    selected_action = Column(String(100), nullable=True)
    tool_parameters = Column(JSON, nullable=True)

    # Execution result
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(JSON, nullable=True)

    # Source context
    trigger_type = Column(String(50), nullable=True)
    source_event_type = Column(String(100), nullable=True)
    source_event_id = Column(String(200), nullable=True)
