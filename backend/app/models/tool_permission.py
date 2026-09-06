from sqlalchemy import Column, String, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class ToolPermission(BaseModel):
    """Links tools/actions to required permissions."""
    __tablename__ = "tool_permissions"

    tool_id = Column(UUID(as_uuid=True), ForeignKey("agent_tools.id"), nullable=False)
    action_id = Column(UUID(as_uuid=True), ForeignKey("tool_actions.id"), nullable=True)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), nullable=False)
    is_required = Column(Boolean, default=True, nullable=False)
