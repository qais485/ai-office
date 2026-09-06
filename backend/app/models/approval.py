from sqlalchemy import Column, String, ForeignKey, Text, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class Approval(BaseModel):
    __tablename__ = "approvals"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    action = Column(String(100), nullable=False)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("agent_tools.id"), nullable=True)
    target = Column(String(255), nullable=True)
    parameters = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)
    risk_level = Column(String(20), default="low", nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    requested_at = Column(String, nullable=True)
    decided_at = Column(String, nullable=True)
    decided_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    decision_notes = Column(Text, nullable=True)
    expires_at = Column(String, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
