from sqlalchemy import Column, String, ForeignKey, JSON, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class AgentPermission(BaseModel):
    __tablename__ = "agent_permissions"
    __table_args__ = (
        UniqueConstraint("agent_id", "permission_id", name="uq_agent_permission"),
    )

    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)
    access_level = Column(String(20), default="allowed", nullable=False)  # allowed, approval_required, denied
    conditions = Column(JSON, nullable=True)  # Future: conditional permission logic
    granted_by = Column(String(100), nullable=True)  # Who granted this permission (template, ceo, etc.)
    notes = Column(String(500), nullable=True)  # Optional notes about why this permission was granted
