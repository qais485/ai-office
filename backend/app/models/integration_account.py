from sqlalchemy import Column, String, Boolean, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class IntegrationAccount(BaseModel):
    __tablename__ = "integration_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "integration_id", name="uq_user_integration"),
    )

    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=True)
    display_name = Column(String(100), nullable=True)
    credentials = Column(JSON, nullable=True)
    config = Column(JSON, nullable=True)
    status = Column(String(50), default="connected", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(String, nullable=True)

    # OAuth2 tokens (encrypted at rest)
    oauth2_access_token = Column(Text, nullable=True)
    oauth2_refresh_token = Column(Text, nullable=True)
    oauth2_token_expiry = Column(String, nullable=True)
    oauth2_scope = Column(String(500), nullable=True)
