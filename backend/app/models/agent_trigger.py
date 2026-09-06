"""Agent Trigger model — persists triggers with execution tracking.

Trigger types:
    MANUAL       — user explicitly asks agent to do something
    SCHEDULED    — agent runs at configured intervals (cron-like)
    INTEGRATION  — external integration event invokes agent
    ROOM         — event/message inside a room invokes agent

Each trigger targets exactly one agent. The agent must be ACTIVE
for the trigger to be processed.
"""
import enum
from sqlalchemy import Column, String, Enum, ForeignKey, Text, JSON, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.models.base import BaseModel


class TriggerType(str, enum.Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    INTEGRATION = "integration"
    ROOM = "room"


class TriggerStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTrigger(BaseModel):
    """A persisted trigger that targets a specific agent."""
    __tablename__ = "agent_triggers"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False, index=True)
    trigger_type = Column(Enum(TriggerType, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    status = Column(Enum(TriggerStatus, values_callable=lambda obj: [e.value for e in obj]), default=TriggerStatus.PENDING, nullable=False)

    # What caused this trigger (e.g. email_id, task_id, manual instruction)
    source_event_type = Column(String(100), nullable=True)
    source_event_id = Column(String(200), nullable=True)

    # Payload for the agent to process
    payload = Column(JSON, nullable=True)

    # Schedule config (only for SCHEDULED triggers)
    schedule_cron = Column(String(100), nullable=True)
    schedule_interval_seconds = Column(JSON, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)

    # Matching rules — which events should trigger this agent
    match_integration = Column(String(100), nullable=True)
    match_event_type = Column(String(100), nullable=True)
    match_room_id = Column(UUID(as_uuid=True), nullable=True)

    # Control
    is_active = Column(Boolean, default=True, nullable=False)
    cooldown_seconds = Column(JSON, default=30, nullable=True)
    max_retries = Column(JSON, default=3, nullable=True)

    # Execution tracking
    total_executions = Column(JSON, default=0, nullable=True)
    last_execution_id = Column(UUID(as_uuid=True), nullable=True)
    last_error = Column(Text, nullable=True)
