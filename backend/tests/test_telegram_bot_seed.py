"""Seed-layer tests for the Telegram Bot customer-chat feature.

Covers:
    - "Telegram Support Agent" template ships both telegram tools + permissions
    - backfill upgrades an EXISTING (pre-upgrade) template row in place
    - telegram_messaging gets its send_messages ToolPermission link (the
      create-time link in seed_tools runs before permissions exist)
    - all seed steps are idempotent (re-run creates no duplicates)
"""
import pytest

from app.models.agent_integration import AgentIntegration
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.models.template import AgentTemplate
from app.models.tool import AgentTool
from app.models.tool_permission import ToolPermission
from app.services.seed_service import (
    seed_integrations,
    seed_permissions,
    seed_telegram_account_tool_permissions,
    seed_templates,
    seed_tools,
)
from app.utils.encryption import encrypt_field

from tests.test_telegram_account_tool import _make_user


def _run_full_seed(db):
    seed_integrations(db)
    seed_tools(db)
    seed_permissions(db)
    seed_telegram_account_tool_permissions(db)
    seed_templates(db)


class TestTelegramSupportTemplate:
    def test_template_ships_bot_and_account_tools(self, api_db):
        _run_full_seed(api_db)

        template = api_db.query(AgentTemplate).filter(
            AgentTemplate.name == "Telegram Support Agent"
        ).first()
        assert template is not None
        assert template.role == "telegram_support"
        for tool in ("telegram_messaging", "telegram_account_messaging", "knowledge_base"):
            assert tool in template.default_tools, tool
        for perm in (
            "send_messages",
            "telegram_account_send",
            "telegram_account_read",
            "read_knowledge",
        ):
            assert perm in template.default_permissions, perm
        assert "Telegram Bot" in template.description

    def test_backfill_upgrades_existing_template_row(self, api_db):
        """User DBs seeded before the upgrade keep the OLD template row —
        seed_templates is create-if-missing, so the backfill must update it."""
        old = AgentTemplate(
            name="Telegram Support Agent",
            role="telegram_support",
            description="Handles customer conversations on Telegram through the connected Telegram user account (MTProto), responds to inquiries, and escalates complex issues to the CEO.",
            default_goals=["old goal"],
            default_rules=["old rule"],
            default_permissions=["telegram_account_send", "telegram_account_read"],
            default_tools=["telegram_account_messaging", "knowledge_base"],
            icon_url="/icons/telegram.svg",
        )
        api_db.add(old)
        api_db.commit()

        _run_full_seed(api_db)

        templates = api_db.query(AgentTemplate).filter(
            AgentTemplate.name == "Telegram Support Agent"
        ).all()
        assert len(templates) == 1  # no duplicate created
        assert templates[0].default_tools == [
            "telegram_messaging",
            "telegram_account_messaging",
            "knowledge_base",
        ]
        assert "send_messages" in templates[0].default_permissions
        assert "Telegram Bot" in templates[0].description

    def test_bot_tool_linked_to_send_messages_permission(self, api_db):
        from app.models.permission import Permission

        _run_full_seed(api_db)

        tool = api_db.query(AgentTool).filter(AgentTool.name == "telegram_messaging").first()
        assert tool is not None
        linked = {
            tp.permission_id for tp in api_db.query(ToolPermission).filter(
                ToolPermission.tool_id == tool.id
            ).all()
        }
        send_messages = api_db.query(Permission).filter(
            Permission.name == "send_messages"
        ).first()
        assert send_messages is not None
        assert send_messages.id in linked

    def test_seed_is_idempotent(self, api_db):
        _run_full_seed(api_db)
        _run_full_seed(api_db)

        assert api_db.query(AgentTemplate).filter(
            AgentTemplate.name == "Telegram Support Agent"
        ).count() == 1
        assert api_db.query(AgentTool).filter(
            AgentTool.name == "telegram_messaging"
        ).count() == 1
        assert api_db.query(Integration).filter(
            Integration.name == "telegram"
        ).count() == 1
        # account tool's permission surface unchanged
        account_tool = api_db.query(AgentTool).filter(
            AgentTool.name == "telegram_account_messaging"
        ).first()
        account_links = api_db.query(ToolPermission).filter(
            ToolPermission.tool_id == account_tool.id
        ).count()
        assert account_links == 2  # telegram_account_send + telegram_account_read

    def test_agent_hired_from_template_maps_to_bot_account(self, api_db):
        """The template's tool list is compatible with an explicit bot-account
        mapping — the wiring the hire flow must produce for Bot-powered chat."""
        _run_full_seed(api_db)
        user = _make_user(api_db)

        integration = api_db.query(Integration).filter(Integration.name == "telegram").first()
        account = IntegrationAccount(
            integration_id=integration.id,
            user_id=user.id,
            display_name="My Bot",
            credentials={"bot_token": encrypt_field("123456789:AAFake")},
            status="connected",
            is_active=True,
        )
        api_db.add(account)
        api_db.flush()

        from tests.test_telegram_account_tool import _map_agent_to_account

        from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
        from app.models.room import OfficeRoom, RoomStatus, RoomVisualStatus
        from uuid import uuid4

        room = OfficeRoom(
            id=uuid4(), name=f"Room {uuid4().hex[:8]}", description="r",
            status=RoomStatus.AVAILABLE, visual_status=RoomVisualStatus.OFFLINE,
            room_type="workspace", capacity="1",
        )
        api_db.add(room)
        agent = AIAgent(
            id=uuid4(), name="Support", role="telegram_support",
            description="hired from template", status=AgentStatus.ACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE, room_id=room.id,
            user_id=user.id,
            tools="telegram_messaging,telegram_account_messaging,knowledge_base",
        )
        api_db.add(agent)
        api_db.flush()

        mapping = _map_agent_to_account(api_db, agent, integration, account)
        assert mapping.integration_account_id == account.id
        assert mapping.agent_id == agent.id
