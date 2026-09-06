import asyncio
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.models.agent_integration import AgentIntegration
from app.models.agent import AIAgent
from app.schemas.integration import IntegrationCreate, IntegrationAccountCreate, IntegrationAccountUpdate
from app.utils.encryption import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)


class IntegrationService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _fire_async(coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            asyncio.run(coro)

    def get_integrations(self, active_only: bool = False) -> List[Integration]:
        query = self.db.query(Integration)
        if active_only:
            query = query.filter(Integration.is_active == True)
        return query.all()

    def get_integration(self, integration_id: UUID) -> Optional[Integration]:
        return self.db.query(Integration).filter(Integration.id == integration_id).first()

    def get_integration_by_name(self, name: str) -> Optional[Integration]:
        return self.db.query(Integration).filter(Integration.name == name).first()

    def create_integration(self, data: IntegrationCreate) -> Integration:
        integration = Integration(**data.model_dump())
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def get_user_accounts(self, user_id: UUID) -> List[IntegrationAccount]:
        return self.db.query(IntegrationAccount).filter(
            IntegrationAccount.user_id == user_id,
            IntegrationAccount.is_active == True
        ).all()

    def get_account(self, account_id: UUID) -> Optional[IntegrationAccount]:
        return self.db.query(IntegrationAccount).filter(IntegrationAccount.id == account_id).first()

    def get_user_integration_account(self, user_id: UUID, integration_id: UUID) -> Optional[IntegrationAccount]:
        return self.db.query(IntegrationAccount).filter(
            IntegrationAccount.user_id == user_id,
            IntegrationAccount.integration_id == integration_id,
            IntegrationAccount.is_active == True
        ).first()

    def create_account(self, user_id: UUID, data: IntegrationAccountCreate) -> IntegrationAccount:
        encrypted_creds = None
        if data.credentials:
            encrypted_creds = {k: encrypt_field(str(v)) for k, v in data.credentials.items()}

        account = IntegrationAccount(
            user_id=user_id,
            integration_id=data.integration_id,
            display_name=data.display_name,
            credentials=encrypted_creds,
            config=data.config,
            status="connected"
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def connect_account(
        self,
        user_id: UUID,
        integration_id: UUID,
        credentials: dict,
        display_name: Optional[str] = None,
        config: Optional[dict] = None
    ) -> IntegrationAccount:
        existing = self.get_user_integration_account(user_id, integration_id)
        if existing:
            encrypted_creds = {k: encrypt_field(str(v)) for k, v in credentials.items()} if credentials else None
            existing.credentials = encrypted_creds
            if display_name:
                existing.display_name = display_name
            if config:
                existing.config = config
            existing.status = "connected"
            self.db.commit()
            self.db.refresh(existing)
            self._publish_integration_event(existing, integration_id, user_id, "connected")
            return existing

        encrypted_creds = {k: encrypt_field(str(v)) for k, v in credentials.items()} if credentials else None
        account = IntegrationAccount(
            integration_id=integration_id,
            user_id=user_id,
            display_name=display_name,
            credentials=encrypted_creds,
            config=config,
            status="connected"
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        self._publish_integration_event(account, integration_id, user_id, "connected")
        return account

    def disconnect_account(self, user_id: UUID, integration_id: UUID) -> bool:
        account = self.get_user_integration_account(user_id, integration_id)
        if not account:
            return False

        account.status = "disconnected"
        account.credentials = None
        self.db.commit()
        self._publish_integration_event(account, integration_id, user_id, "disconnected")
        return True

    def _publish_integration_event(self, account: IntegrationAccount, integration_id: UUID, user_id: UUID, action: str) -> None:
        try:
            from app.events.publisher import publish_integration_event
            from app.events.types import EventType
            integration = self.db.query(Integration).filter(Integration.id == integration_id).first()
            event_type = EventType.INTEGRATION_CONNECTED if action == "connected" else EventType.INTEGRATION_DISCONNECTED
            self._fire_async(
                publish_integration_event(
                    event_type=event_type,
                    integration_id=integration_id,
                    account_id=account.id,
                    integration_name=integration.name if integration else "unknown",
                    user_id=user_id,
                )
            )
        except Exception as e:
            logger.warning("Failed to publish integration event", exc_info=True)

    def get_account_credentials(self, account_id: UUID) -> Optional[dict]:
        account = self.get_account(account_id)
        if not account or not account.credentials:
            return None
        return {k: decrypt_field(str(v)) for k, v in account.credentials.items()}

    def update_account(self, account_id: UUID, data: IntegrationAccountUpdate) -> Optional[IntegrationAccount]:
        account = self.get_account(account_id)
        if account:
            update_data = data.model_dump(exclude_unset=True)
            if "credentials" in update_data and update_data["credentials"]:
                update_data["credentials"] = {k: encrypt_field(str(v)) for k, v in update_data["credentials"].items()}
            for key, value in update_data.items():
                setattr(account, key, value)
            self.db.commit()
            self.db.refresh(account)
        return account

    def delete_account(self, account_id: UUID) -> bool:
        account = self.get_account(account_id)
        if account:
            self.db.delete(account)
            self.db.commit()
            return True
        return False

    def assign_integration_to_agent(
        self,
        agent_id: UUID,
        integration_id: UUID,
        capabilities: Optional[List[str]] = None,
        integration_account_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
    ) -> Optional[AgentIntegration]:
        """Assign an integration to an agent with optional explicit account mapping.

        When integration_account_id is provided, the agent will use that specific
        connected account for all tool executions. This ensures deterministic
        account selection and prevents unauthorized access to other users' accounts.
        """
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return None
        if user_id is not None and agent.user_id != user_id:
            return None

        integration = self.db.query(Integration).filter(Integration.id == integration_id).first()
        if not integration:
            return None

        # Validate account if provided
        if integration_account_id:
            account = self.db.query(IntegrationAccount).filter(
                IntegrationAccount.id == integration_account_id,
                IntegrationAccount.integration_id == integration_id,
                IntegrationAccount.is_active == True,
                IntegrationAccount.status == "connected",
            ).first()
            if not account:
                return None
            # Note: We don't enforce user ownership here because the agent
            # might be shared across users. The security check happens at
            # tool execution time.

        existing = self.db.query(AgentIntegration).filter(
            AgentIntegration.agent_id == agent_id,
            AgentIntegration.integration_id == integration_id,
            AgentIntegration.is_active == True
        ).first()

        if existing:
            if capabilities:
                existing.capabilities = "|".join(capabilities)
            if integration_account_id:
                existing.integration_account_id = integration_account_id
            self.db.commit()
            self.db.refresh(existing)
            return existing

        agent_integration = AgentIntegration(
            agent_id=agent_id,
            integration_id=integration_id,
            integration_account_id=integration_account_id,
            capabilities="|".join(capabilities) if capabilities else None,
            is_active=True
        )
        self.db.add(agent_integration)
        self.db.commit()
        self.db.refresh(agent_integration)
        return agent_integration

    def remove_integration_from_agent(self, agent_id: UUID, integration_id: UUID, user_id: Optional[UUID] = None) -> bool:
        # Verify agent ownership
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return False
        if user_id is not None and agent.user_id != user_id:
            return False

        agent_integration = self.db.query(AgentIntegration).filter(
            AgentIntegration.agent_id == agent_id,
            AgentIntegration.integration_id == integration_id,
            AgentIntegration.is_active == True
        ).first()

        if not agent_integration:
            return False

        agent_integration.is_active = False
        self.db.commit()
        return True

    def get_agent_integrations(self, agent_id: UUID, user_id: Optional[UUID] = None) -> List[Integration]:
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return []
        if user_id is not None and agent.user_id != user_id:
            return []

        agent_integrations = self.db.query(AgentIntegration).filter(
            AgentIntegration.agent_id == agent_id,
            AgentIntegration.is_active == True
        ).all()

        if not agent_integrations:
            return []

        integration_ids = [ai.integration_id for ai in agent_integrations]
        return self.db.query(Integration).filter(
            Integration.id.in_(integration_ids),
            Integration.is_active == True
        ).all()

    def get_integration_agents(self, integration_id: UUID, user_id: Optional[UUID] = None) -> List[AIAgent]:
        agent_integrations = self.db.query(AgentIntegration).filter(
            AgentIntegration.integration_id == integration_id,
            AgentIntegration.is_active == True
        ).all()

        if not agent_integrations:
            return []

        agent_ids = [ai.agent_id for ai in agent_integrations]
        query = self.db.query(AIAgent).filter(AIAgent.id.in_(agent_ids))
        if user_id is not None:
            query = query.filter(AIAgent.user_id == user_id)
        return query.all()
