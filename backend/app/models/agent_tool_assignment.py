from sqlalchemy import Column, Boolean, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class AgentToolAssignment(BaseModel):
    """Tracks which tools are assigned to which agents with per-agent configuration."""
    __tablename__ = "agent_tool_assignments"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("agent_tools.id"), nullable=False)
    tool_name = Column(String(100), nullable=True)  # Denormalized for fast lookup
    is_active = Column(Boolean, default=True, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    config = Column(JSON, nullable=True)  # Per-agent tool configuration
