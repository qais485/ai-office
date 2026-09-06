from sqlalchemy import Column, String, Boolean, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class ToolAction(BaseModel):
    """Individual actions that can be performed by a tool."""
    __tablename__ = "tool_actions"

    tool_id = Column(UUID(as_uuid=True), ForeignKey("agent_tools.id"), nullable=False)
    name = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    risk_level = Column(String(20), default="low", nullable=False)
    requires_approval = Column(Boolean, default=False, nullable=False)
    input_schema = Column(JSON, nullable=True)
    output_schema = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
