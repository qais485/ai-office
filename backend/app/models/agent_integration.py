from sqlalchemy import Column, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class AgentIntegration(BaseModel):
    """Tracks which integrations are assigned to which agents.

    The optional integration_account_id field explicitly links an agent
    to a specific connected account (e.g., a specific Gmail account).
    When set, tool execution uses THIS account instead of picking any
    active account for the integration.
    """
    __tablename__ = "agent_integrations"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("ai_agents.id"), nullable=False)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False)

    # Explicit account mapping — deterministic account selection
    integration_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("integration_accounts.id"),
        nullable=True,
    )

    capabilities = Column(Text, nullable=True)  # Pipe-separated list of granted capabilities
    is_active = Column(Boolean, default=True, nullable=False)
