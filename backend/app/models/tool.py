from sqlalchemy import Column, String, Boolean, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class AgentTool(BaseModel):
    __tablename__ = "agent_tools"

    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="general")
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=True)
    input_schema = Column(JSON, nullable=True)
    output_schema = Column(JSON, nullable=True)
    risk_level = Column(String(20), default="low", nullable=False)
    requires_approval = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(String(20), default="1.0.0", nullable=False)
