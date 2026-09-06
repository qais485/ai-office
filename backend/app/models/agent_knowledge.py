from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class AgentKnowledgeAccess(BaseModel):
    __tablename__ = "agent_knowledge_access"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False)
    knowledge_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_sources.id"), nullable=False)
    access_level = Column(String(20), default="read", nullable=False)
    granted_by = Column(String(50), nullable=True, default="system")
