"""Tests for the telegram_account_messaging agent tool (MTProto account).

Security contract under test:
    - the tool is seeded and linked to the telegram_account integration
    - execution goes through the explicitly selected Integration Account
      (AgentIntegration.integration_account_id) with agent permissions enforced
    - decrypted credentials (api_id / api_hash / session) reach ONLY the
      provider server-side and never appear in agent-visible results
"""
from uuid import uuid4

import pytest

from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.agent_integration import AgentIntegration
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.models.permission import Permission
from app.models.room import OfficeRoom, RoomStatus, RoomVisualStatus
from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.models.tool_permission import ToolPermission
from app.models.user import User
from app.services.integration_providers.base import ProviderResult
from app.services.integration_providers.registry import get_provider
from app.services.integration_providers.telegram_account import TelegramAccountProvider
from app.services.permission_service import PermissionService
from app.schemas.permission import AgentPermissionCreate
from app.services.seed_service import (
    seed_integrations,
    seed_permissions,
    seed_telegram_account_tool_permissions,
    seed_tools,
)
from app.services.tool_execution_service import ToolExecutionService
from app.utils.encryption import encrypt_field

API_ID = "1234567"
API_HASH = "0123456789abcdef0123456789abcdef"
SESSION = "1BQANOTEuMTA4LjUuMjQ5iQHAspK10-L8wC0GEb8UvKQm0p4TEsYTLp3kFRN1S0gyhFVBpFqQZ3FtTMhTAcHJpdmF0ZQ"


# ---------------------------------------------------------------------------
# World builders
# ---------------------------------------------------------------------------


def _seed_world(api_db):
    seed_integrations(api_db)
    seed_tools(api_db)
    seed_permissions(api_db)
    seed_telegram_account_tool_permissions(api_db)


def _make_user(api_db, email="ceo@test.com", role="user"):
    user = User(id=uuid4(), email=email, name="Test User", role=role, is_active=True)
    api_db.add(user)
    api_db.flush()
    return user


def _make_active_agent(api_db, user, tool_name="telegram_account_messaging"):
    room = OfficeRoom(
        id=uuid4(),
        name=f"Room {uuid4().hex[:8]}",
        description="Test room",
        status=RoomStatus.AVAILABLE,
        visual_status=RoomVisualStatus.OFFLINE,
        room_type="workspace",
        capacity="1",
    )
    api_db.add(room)
    agent = AIAgent(
        id=uuid4(),
        name="Telegram Agent",
        role="assistant",
        description="Agent with a telegram account",
        status=AgentStatus.ACTIVE,
        lifecycle_status=LifecycleStatus.ACTIVE,
        room_id=room.id,
        user_id=user.id,
        tools=tool_name,
    )
    api_db.add(agent)
    api_db.flush()
    return agent


def _make_connected_account(api_db, integration, user, api_id=API_ID, display_name="My Telegram"):
    account = IntegrationAccount(
        integration_id=integration.id,
        user_id=user.id,
        display_name=display_name,
        credentials={
            "api_id": encrypt_field(api_id),
            "api_hash": encrypt_field(API_HASH),
            "session": encrypt_field(SESSION),
        },
        status="connected",
        is_active=True,
    )
    api_db.add(account)
    api_db.flush()
    return account


def _map_agent_to_account(api_db, agent, integration, account):
    mapping = AgentIntegration(
        agent_id=agent.id,
        integration_id=integration.id,
        integration_account_id=account.id,
        is_active=True,
    )
    api_db.add(mapping)
    api_db.flush()
    return mapping


def _grant_agent_permissions(api_db, agent, names):
    service = PermissionService(api_db)
    for name in names:
        permission = api_db.query(Permission).filter(Permission.name == name).first()
        service.set_agent_permission(
            agent.id,
            AgentPermissionCreate(permission_id=permission.id, access_level="allowed"),
            granted_by="test",
        )


def _telegram_account_integration(api_db):
    return api_db.query(Integration).filter(Integration.name == "telegram_account").first()


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


class TestSeeding:
    def test_tool_created_and_linked_to_telegram_account(self, api_db):
        _seed_world(api_db)

        tool = api_db.query(AgentTool).filter(AgentTool.name == "telegram_account_messaging").first()
        assert tool is not None
        assert tool.integration_id == _telegram_account_integration(api_db).id
        assert tool.integration_id is not None

    def test_tool_actions_match_provider_actions(self, api_db):
        _seed_world(api_db)

        tool = api_db.query(AgentTool).filter(AgentTool.name == "telegram_account_messaging").first()
        actions = {a.name: a for a in api_db.query(ToolAction).filter(ToolAction.tool_id == tool.id).all()}
        assert set(actions) == {"send_message", "read_history"}
        assert actions["send_message"].risk_level == "medium"
        assert actions["read_history"].risk_level == "low"

    def test_tool_permissions_linked(self, api_db):
        _seed_world(api_db)

        tool = api_db.query(AgentTool).filter(AgentTool.name == "telegram_account_messaging").first()
        linked = {
            p.name
            for p in (
                api_db.query(Permission)
                .join(ToolPermission, ToolPermission.permission_id == Permission.id)
                .filter(ToolPermission.tool_id == tool.id)
                .all()
            )
        }
        assert linked == {"telegram_account_send", "telegram_account_read"}

    def test_permission_linking_is_idempotent(self, api_db):
        _seed_world(api_db)
        seed_telegram_account_tool_permissions(api_db)
        seed_telegram_account_tool_permissions(api_db)

        tool = api_db.query(AgentTool).filter(AgentTool.name == "telegram_account_messaging").first()
        count = api_db.query(ToolPermission).filter(ToolPermission.tool_id == tool.id).count()
        assert count == 2


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_telegram_account_provider_registered(self):
        provider = get_provider("telegram_account")
        assert isinstance(provider, TelegramAccountProvider)

    def test_provider_supports_tool_actions(self):
        provider = TelegramAccountProvider()
        # provider.execute_action rejects unknown actions; these two must not error
        # before the credentials check — validate via the handlers dict indirectly.
        handlers = {
            "send_message": provider._send_message,
            "read_history": provider._read_history,
        }
        assert callable(handlers["send_message"])
        assert callable(handlers["read_history"])


# ---------------------------------------------------------------------------
# Execution through the security pipeline
# ---------------------------------------------------------------------------


class RecordingProvider:
    def __init__(self, result=None):
        self.calls = []
        self._result = result or ProviderResult(success=True, data={"message_id": 7, "chat_id": 42})

    async def execute_action(self, action, parameters, access_token=None, credentials=None):
        self.calls.append(
            {
                "action": action,
                "parameters": dict(parameters or {}),
                "access_token": access_token,
                "credentials": credentials,
            }
        )
        return self._result


class TestExecution:
    def test_executes_via_selected_account_without_leaking_credentials(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)
        integration = _telegram_account_integration(api_db)
        account = _make_connected_account(api_db, integration, user)
        _map_agent_to_account(api_db, agent, integration, account)
        _grant_agent_permissions(api_db, agent, ["telegram_account_send", "telegram_account_read"])

        recorder = RecordingProvider()
        import app.services.integration_providers.registry as registry
        monkeypatch.setattr(registry, "get_provider", lambda name: recorder)

        result = ToolExecutionService(api_db).execute_tool(
            agent_id=agent.id,
            tool_name="telegram_account_messaging",
            action="send_message",
            parameters={"chat_id": "@testchat", "text": "hello", "_internal": "strip-me"},
            reason="test",
        )

        assert result["success"] is True
        assert result["data"]["message_id"] == 7

        call = recorder.calls[0]
        assert call["action"] == "send_message"
        # credentials are decrypted server-side for the provider only
        assert call["credentials"] == {"api_id": API_ID, "api_hash": API_HASH, "session": SESSION}
        # underscore-prefixed internal keys never reach the provider
        assert "_internal" not in call["parameters"]
        # agent-visible result carries no credential material
        serialized = str(result)
        assert API_HASH not in serialized
        assert SESSION not in serialized

    def test_selected_account_mapping_is_deterministic(self, api_db, monkeypatch):
        _seed_world(api_db)
        owner = _make_user(api_db)
        other = _make_user(api_db, email="other@test.com", role="user")
        agent = _make_active_agent(api_db, owner)
        integration = _telegram_account_integration(api_db)
        account_a = _make_connected_account(api_db, integration, owner, api_id="1111111")
        _make_connected_account(api_db, integration, other, api_id="2222222")
        _map_agent_to_account(api_db, agent, integration, account_a)
        _grant_agent_permissions(api_db, agent, ["telegram_account_send", "telegram_account_read"])

        recorder = RecordingProvider()
        import app.services.integration_providers.registry as registry
        monkeypatch.setattr(registry, "get_provider", lambda name: recorder)

        result = ToolExecutionService(api_db).execute_tool(
            agent_id=agent.id,
            tool_name="telegram_account_messaging",
            action="send_message",
            parameters={"chat_id": "@testchat", "text": "hi"},
        )

        assert result["success"] is True
        # two connected accounts exist, but the explicit mapping picks account A
        assert recorder.calls[0]["credentials"]["api_id"] == "1111111"

    def test_missing_agent_permission_denied(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)
        integration = _telegram_account_integration(api_db)
        account = _make_connected_account(api_db, integration, user)
        _map_agent_to_account(api_db, agent, integration, account)
        # no permission grants on purpose

        recorder = RecordingProvider()
        import app.services.integration_providers.registry as registry
        monkeypatch.setattr(registry, "get_provider", lambda name: recorder)

        result = ToolExecutionService(api_db).execute_tool(
            agent_id=agent.id,
            tool_name="telegram_account_messaging",
            action="send_message",
            parameters={"chat_id": "@testchat", "text": "hi"},
        )

        assert result["success"] is False
        assert result["code"] == "PERMISSION_DENIED"
        assert recorder.calls == []


# ---------------------------------------------------------------------------
# Provider-level secret hygiene
# ---------------------------------------------------------------------------


class _FakeSession:
    def __init__(self, payload=None):
        self._payload = payload or ""

    def save(self):
        return self._payload


class _LeakyFakeClient:
    """Fake Telethon client whose errors echo the session and api_hash."""

    def __init__(self, session, api_id, api_hash):
        self.session = session
        self.api_id = api_id
        self.api_hash = api_hash

    async def connect(self):
        return True

    async def disconnect(self):
        return True

    async def is_user_authorized(self):
        return True

    async def get_entity(self, chat_id):
        raise RuntimeError(
            f"entity lookup failed for session {SESSION} and api_hash {API_HASH}"
        )

    async def send_message(self, entity, text):  # pragma: no cover
        return None


class TestSecretHygiene:
    def test_provider_errors_never_expose_api_hash_or_session(self, monkeypatch):
        import app.services.integration_providers.telegram_account as ta_module
        monkeypatch.setattr(
            ta_module,
            "_load_telethon",
            lambda: (_LeakyFakeClient, _FakeSession),
        )
        provider = TelegramAccountProvider()

        from app.utils.async_utils import run_async

        outcome = run_async(
            provider.execute_action(
                "send_message",
                {"chat_id": "@testchat", "text": "hi"},
                credentials={"api_id": API_ID, "api_hash": API_HASH, "session": SESSION},
            )
        )

        assert outcome.success is False
        assert outcome.error is not None
        assert SESSION not in outcome.error
        assert API_HASH not in outcome.error
        assert "***" in outcome.error
