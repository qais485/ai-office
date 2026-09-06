from sqlalchemy import Column, String, Boolean, Text, JSON

from app.models.base import BaseModel


class AgentTemplate(BaseModel):
    __tablename__ = "agent_templates"

    name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    default_goals = Column(JSON, nullable=True)
    default_rules = Column(JSON, nullable=True)
    default_permissions = Column(JSON, nullable=True)
    default_tools = Column(JSON, nullable=True)
    default_knowledge = Column(JSON, nullable=True)
    icon_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
