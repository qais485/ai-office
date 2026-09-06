from sqlalchemy import Column, String, Boolean, ForeignKey, Text, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.models.base import BaseModel


class RiskRule(BaseModel):
    __tablename__ = "risk_rules"
    __table_args__ = (
        Index("ix_risk_rules_action_name", "action_name"),
        Index("ix_risk_rules_tool_id", "tool_id"),
        Index("ix_risk_rules_is_active", "is_active"),
    )

    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    action_name = Column(String(100), nullable=True)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("agent_tools.id"), nullable=True)
    risk_level = Column(String(20), default="medium", nullable=False)
    requires_approval = Column(Boolean, default=False, nullable=False)
    conditions = Column(JSON, nullable=True)
    priority = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
