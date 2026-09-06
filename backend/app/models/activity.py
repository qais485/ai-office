from sqlalchemy import Column, String, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class AgentActivity(BaseModel):
    __tablename__ = "agent_activities"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False)
    activity_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    tool_name = Column(String, nullable=True)
    status = Column(String, nullable=True)
