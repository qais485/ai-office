from sqlalchemy import Column, String, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class AgentCollaboration(BaseModel):
    __tablename__ = "agent_collaborations"

    from_agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False)
    to_agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    message = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
