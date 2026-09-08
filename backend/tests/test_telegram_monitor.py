"""Tests for the Telegram Account (MTProto) inbound auto-reply loop.

Covers:
    - TelegramMonitorService: watermarks, baseline pass, trigger firing,
      flood cap, group/bot/outgoing filtering, secret scrubbing
    - agent_runtime telegram branch: bot-sender skip, chat pinning +
      reply-guard tagging, AUTOMATED classification → CEO approval
    - EmailReplyGuard telegram category mapping
    - event wiring (type, publisher, trigger handler registration)
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.agent_trigger import AgentTrigger, TriggerType
from app.models.email import EmailMessage
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.models.telegram_sync_state import TelegramSyncState
from app.services.tool_execution_service import EmailReplyGuard
from app.utils.encryption import encrypt_field

from tests.test_telegram_account_tool import (
    API_HASH,
    API_ID,
    SESSION,
    _make_active_agent,
    _make_connected_account,
    _make_user,
    _map_agent_to_account,
    _seed_world,
    _telegram_account_integration,
)

# ---------------------------------------------------------------------------
# Fake Telethon world
# ---------------------------------------------------------------------------


class FakeEntity:
    def __init__(self, bot=False, username="alice", first_name="Alice"):
        self.bot = bot
        self.username = username
        self.first_name = first_name


class FakeMessage:
    def __init__(self, id, message="hello", out=False, sender_id=555, action=None):
        self.id = id
        self.message = message
        self.out = out
        self.sender_id = sender_id
        self.action = action
        self.date = datetime.now(timezone.utc)


class FakeDialog:
    def __init__(self, id, entity, name="Alice", is_user=True):
        self.id = id
        self.entity = entity
        self.name = name
        self.is_user = is_user


def _make_fake_client(dialogs_and_messages):
    """Build a FakeClient class over {dialog: [messages]} mutable state."""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def is_user_authorized(self):
            return True

        async def iter_dialogs(self):
            for dialog, messages in dialogs_and_messages.items():
                yield dialog

        async def get_messages(self, entity, limit=20):
            for dialog, messages in dialogs_and_messages.items():
                if dialog.entity is entity or dialog.id == getattr(entity, "_dialog_id", None):
                    return list(messages)
            return []

    return FakeClient


# ---------------------------------------------------------------------------
# World builders (monitor-specific)
# ---------------------------------------------------------------------------


def _monitor_account(api_db, user, with_session=True):
    integration = _telegram_account_integration(api_db)
    credentials = {
        "api_id": encrypt_field(API_ID),
        "api_hash": encrypt_field(API_HASH),
    }
    if with_session:
        credentials["session"] = encrypt_field(SESSION)
    account = IntegrationAccount(
        integration_id=integration.id,
        user_id=user.id,
        display_name="My Telegram",
        credentials=credentials,
        status="connected",
        is_active=True,
    )
    api_db.add(account)
    api_db.flush()
    return account


def _run_async(coro):
    """Run a coroutine on a live loop.

    pytest-asyncio tears the current loop down between async tests, so a
    plain ``asyncio.get_event_loop()`` raises RuntimeError once an async test
    has run earlier in the session — rebuild the loop when needed.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _run_check(api_db, account, fake_client_cls, monkeypatch):
    import app.services.telegram_monitor_service as tm

    class FakeStringSession:
        def __init__(self, payload=None):
            self.payload = payload

    monkeypatch.setattr(tm, "_load_telethon", lambda: (fake_client_cls, FakeStringSession))
    return _run_async(tm.TelegramMonitorService(api_db).check_account(account.id))


# ---------------------------------------------------------------------------
# check_account behaviour
# ---------------------------------------------------------------------------


class TestCheckAccountSkips:
    def test_skips_without_bound_session(self, api_db):
        _seed_world(api_db)
        user = _make_user(api_db)
        account = _monitor_account(api_db, user, with_session=False)

        import asyncio
        import app.services.telegram_monitor_service as tm

        result = _run_async(tm.TelegramMonitorService(api_db).check_account(account.id)
        )
        assert "no MTProto session bound" in result["skipped"]

    def test_skips_when_telethon_not_installed(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        account = _monitor_account(api_db, user)

        import app.services.telegram_monitor_service as tm

        monkeypatch.setattr(tm, "_load_telethon", lambda: (None, None))
        import asyncio

        result = _run_async(tm.TelegramMonitorService(api_db).check_account(account.id)
        )
        assert "telethon is not installed" in result["skipped"]

    def test_skips_disconnected_account(self, api_db):
        _seed_world(api_db)
        user = _make_user(api_db)
        integration = _telegram_account_integration(api_db)
        account = IntegrationAccount(
            integration_id=integration.id,
            user_id=user.id,
            display_name="Dead",
            credentials={"api_id": encrypt_field(API_ID)},
            status="disconnected",
            is_active=True,
        )
        api_db.add(account)
        api_db.flush()

        import app.services.telegram_monitor_service as tm
        import asyncio

        result = _run_async(tm.TelegramMonitorService(api_db).check_account(account.id)
        )
        assert "not connected" in result["skipped"]


class TestWatermarkBaseline:
    def test_baseline_pass_records_watermark_without_firing(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)
        account = _monitor_account(api_db, user)
        _map_agent_to_account(api_db, agent, _telegram_account_integration(api_db), account)

        dialog = FakeDialog(111, FakeEntity(), name="Alice")
        msgs = {dialog: [FakeMessage(10, "hello from alice")]}
        result = _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)

        assert result["new_messages"] == 0
        state = api_db.query(TelegramSyncState).filter(
            TelegramSyncState.integration_account_id == account.id
        ).first()
        assert state.last_seen_message_ids == {"111": 10}
        assert api_db.query(AgentTrigger).filter(
            AgentTrigger.source_event_type == "telegram_message_received"
        ).count() == 0

    def test_new_message_after_baseline_fires_trigger(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)
        account = _monitor_account(api_db, user)
        _map_agent_to_account(api_db, agent, _telegram_account_integration(api_db), account)

        dialog = FakeDialog(111, FakeEntity(), name="Alice")
        msgs = {dialog: [FakeMessage(10, "baseline")]}
        _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)

        msgs[dialog].append(FakeMessage(11, "new customer question"))
        result = _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)

        assert result["new_messages"] == 1
        trigger = api_db.query(AgentTrigger).filter(
            AgentTrigger.source_event_type == "telegram_message_received"
        ).first()
        assert trigger is not None
        assert trigger.source_event_id == "111:11"
        assert trigger.payload["chat_id"] == "111"
        assert trigger.payload["text"] == "new customer question"
        assert trigger.payload["from_address"] == "@alice"

    def test_same_message_not_fired_twice(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)
        account = _monitor_account(api_db, user)
        _map_agent_to_account(api_db, agent, _telegram_account_integration(api_db), account)

        dialog = FakeDialog(111, FakeEntity(), name="Alice")
        msgs = {dialog: [FakeMessage(10, "baseline")]}
        _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)
        msgs[dialog].append(FakeMessage(11, "new question"))
        _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)
        # third cycle with unchanged history → nothing new
        result = _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)
        assert result["new_messages"] == 0


class TestSecurityGuards:
    def test_outgoing_and_bot_messages_never_fire(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)
        account = _monitor_account(api_db, user)
        _map_agent_to_account(api_db, agent, _telegram_account_integration(api_db), account)

        bot_dialog = FakeDialog(200, FakeEntity(bot=True, username="somebot"), is_user=True)
        private = FakeDialog(111, FakeEntity(), name="Alice")
        msgs = {
            bot_dialog: [FakeMessage(5, "bot msg")],
            private: [FakeMessage(10, "baseline")],
        }
        _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)

        # new messages on both dialogs: bot's is never processed, agent's own
        # outgoing message is ignored
        msgs[bot_dialog].append(FakeMessage(6, "bot reply"))
        msgs[private].append(FakeMessage(11, "i am the account owner", out=True))
        result = _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)
        assert result["new_messages"] == 0

    def test_groups_ignored_by_default(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)
        account = _monitor_account(api_db, user)
        _map_agent_to_account(api_db, agent, _telegram_account_integration(api_db), account)

        group = FakeDialog(300, FakeEntity(username=None, first_name="Group"), name="Group", is_user=False)
        msgs = {group: [FakeMessage(1, "group baseline")]}
        _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)

        msgs[group].append(FakeMessage(2, "new group message"))
        result = _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)
        assert result["new_messages"] == 0

    def test_flood_cap_limits_triggers_per_cycle(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)
        account = _monitor_account(api_db, user)
        _map_agent_to_account(api_db, agent, _telegram_account_integration(api_db), account)

        dialog = FakeDialog(111, FakeEntity(), name="Alice")
        msgs = {dialog: [FakeMessage(10, "baseline")]}
        _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)

        for i in range(1, 16):
            msgs[dialog].append(FakeMessage(10 + i, f"spam {i}"))
        result = _run_check(api_db, account, _make_fake_client(msgs), monkeypatch)
        assert result["new_messages"] == 10  # TELEGRAM_MAX_TRIGGERS_PER_CYCLE


class TestSecretHygiene:
    def test_record_failure_scrubs_secrets(self, api_db):
        _seed_world(api_db)
        user = _make_user(api_db)
        account = _monitor_account(api_db, user)

        import app.services.telegram_monitor_service as tm

        service = tm.TelegramMonitorService(api_db)
        state = service._load_or_create_state(account)  # ensure the row exists

        leaky = f"AuthKeyDuplicatedError: session {SESSION} hash {API_HASH} broken"
        service.record_failure(
            account.id, tm._scrub_secrets(leaky, {"api_hash": API_HASH, "session": SESSION})
        )

        state = api_db.query(TelegramSyncState).filter(
            TelegramSyncState.integration_account_id == account.id
        ).first()
        assert state.consecutive_errors == 1
        assert SESSION not in (state.sync_error or "")
        assert API_HASH not in (state.sync_error or "")
        assert "***" in state.sync_error


# ---------------------------------------------------------------------------
# agent_runtime telegram branch
# ---------------------------------------------------------------------------


def _make_telegram_trigger(api_db, agent, payload):
    from app.services.trigger_service import TriggerService

    service = TriggerService(api_db)
    trigger = service.create_trigger(
        agent_id=agent.id,
        trigger_type=TriggerType.INTEGRATION,
        payload=payload,
        source_event_type="telegram_message_received",
        source_event_id=f"{payload['chat_id']}:{payload['message_id']}",
        match_integration="telegram_account",
        match_event_type="telegram_message_received",
    )
    execution = service.start_execution(trigger)
    return trigger, execution


class TestAgentRuntimeTelegram:
    def _loop(self, agent):
        from app.services.agent_runtime import AgentLoop, agent_runtime

        loop = AgentLoop(str(agent.id), agent_runtime)
        return loop

    @pytest.mark.asyncio
    async def test_bot_sender_skipped_without_llm(self, api_db):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)

        trigger, execution = _make_telegram_trigger(api_db, agent, {
            "message_id": "11", "chat_id": "111", "chat_title": "Chat",
            "sender_id": "999", "from_address": "@somebot", "text": "hi",
            "is_bot": True, "account_id": "",
        })
        from app.services.trigger_service import TriggerService

        loop = self._loop(agent)
        result = await loop._reason_and_act(
            api_db, agent, trigger, execution, TriggerService(api_db), task=None
        )
        assert result["success"] is True
        assert "Bot message" in result["message"]
        from app.models.trigger_execution import TriggerExecution, ExecutionStatus

        fresh = api_db.query(TriggerExecution).filter(TriggerExecution.id == execution.id).first()
        assert fresh.selected_action is None

    @pytest.mark.asyncio
    async def test_reply_pinned_to_chat_and_guard_tagged(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)

        trigger, execution = _make_telegram_trigger(api_db, agent, {
            "message_id": "11", "chat_id": "111", "chat_title": "Chat",
            "sender_id": "555", "from_address": "@alice",
            "text": "hello, i need help", "account_id": "",
        })

        import app.core.llm as llm_module
        import app.services.tool_execution_service as tes_module

        class FakeLLM:
            def invoke(self, prompt):
                return type("Resp", (), {"content": json.dumps({
                    "action": "send_message",
                    "tool": "telegram_account_messaging",
                    "parameters": {"chat_id": "", "text": "Hi! How can I help?"},
                    "reason": "customer question",
                    "email_class": "HUMAN",
                })})()

        class FakeExecService:
            def __init__(self, db):
                pass

            def execute_tool(self, **kwargs):
                FakeExecService.last = kwargs
                return {"success": True, "data": {"message_id": 7}}

        monkeypatch.setattr(llm_module, "get_llm", lambda: FakeLLM())
        monkeypatch.setattr(tes_module, "ToolExecutionService", FakeExecService)

        from app.services.trigger_service import TriggerService

        loop = self._loop(agent)
        result = await loop._reason_and_act(
            api_db, agent, trigger, execution, TriggerService(api_db), task=None
        )

        assert result["success"] is True
        kwargs = FakeExecService.last
        assert kwargs["action"] == "send_message"
        assert kwargs["parameters"]["chat_id"] == "111"  # pinned to source chat
        assert kwargs["parameters"]["_reply_to_message_id"] == "tg:111:11"

    @pytest.mark.asyncio
    async def test_automated_reply_held_for_ceo_approval(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user)

        trigger, execution = _make_telegram_trigger(api_db, agent, {
            "message_id": "12", "chat_id": "111", "chat_title": "Chat",
            "sender_id": "1", "from_address": "@newsletterbot",
            "text": "You have a new notification", "account_id": "",
        })

        import app.core.llm as llm_module
        import app.services.tool_execution_service as tes_module

        class FakeLLM:
            def invoke(self, prompt):
                return type("Resp", (), {"content": json.dumps({
                    "action": "send_message",
                    "tool": "telegram_account_messaging",
                    "parameters": {"text": "Thanks!"},
                    "reason": "automated message",
                    "email_class": "AUTOMATED",
                })})()

        class FakeExecService:
            def __init__(self, db):
                pass

            def execute_tool(self, **kwargs):
                FakeExecService.last = kwargs
                return {"success": True, "requires_approval": True, "approval_id": "abc"}

        monkeypatch.setattr(llm_module, "get_llm", lambda: FakeLLM())
        monkeypatch.setattr(tes_module, "ToolExecutionService", FakeExecService)

        from app.services.trigger_service import TriggerService

        loop = self._loop(agent)
        result = await loop._reason_and_act(
            api_db, agent, trigger, execution, TriggerService(api_db), task=None
        )

        assert result.get("requires_approval") is True
        assert "held for CEO approval" in result["message"]
        assert "Telegram" in result["message"]
        assert FakeExecService.last.get("force_approval") is True


# ---------------------------------------------------------------------------
# EmailReplyGuard telegram support
# ---------------------------------------------------------------------------


class TestReplyGuardTelegram:
    def test_guard_category_mapping(self):
        assert EmailReplyGuard.guard_category("send_email") == "reply_guard"
        assert (
            EmailReplyGuard.guard_category("send_message", "telegram_account_messaging")
            == "reply_guard_telegram"
        )
        # other send_message tools are NOT guarded (no runtime tag anyway)
        assert EmailReplyGuard.guard_category("send_message", "chat_tool") is None
        assert EmailReplyGuard.guard_category("send_message") is None

    def test_telegram_reply_recorded_and_blocked(self, api_db):
        source = "tg:111:11"
        guard = EmailReplyGuard(db=api_db)
        assert guard.has_replied(source, EmailReplyGuard.TELEGRAM_GUARD_CATEGORY) is False

        guard.record_reply(source, "@alice", EmailReplyGuard.TELEGRAM_GUARD_CATEGORY)

        assert guard.has_replied(source, EmailReplyGuard.TELEGRAM_GUARD_CATEGORY) is True
        # email namespace unaffected — same numeric id cannot collide
        assert guard.has_replied("111:11") is False
        row = api_db.query(EmailMessage).filter(
            EmailMessage.conversation_id == source,
            EmailMessage.category == "reply_guard_telegram",
        ).first()
        assert row is not None


# ---------------------------------------------------------------------------
# Event wiring
# ---------------------------------------------------------------------------


class TestEventWiring:
    def test_event_type_and_registration(self):
        from app.events.types import EventType

        assert EventType.TELEGRAM_MESSAGE_RECEIVED.value == "telegram_message_received"

        from app.events import triggers as triggers_module
        from app.events.bus import event_bus

        triggers_module.register_trigger_handlers()
        handlers = event_bus._handlers.get(EventType.TELEGRAM_MESSAGE_RECEIVED, [])
        assert triggers_module.handle_telegram_message_received in handlers

    @pytest.mark.asyncio
    async def test_publish_smoke_end_to_end(self):
        from app.events.publisher import publish_telegram_message_received
        from app.events.types import EventType, TelegramMessageEvent

        event = TelegramMessageEvent(message_id="1", chat_id="111", text="hi")
        assert event.data["chat_id"] == "111"

        # runtime is not running in tests → handler returns early, no crash
        await publish_telegram_message_received(
            message_id="1", chat_id="111", chat_title="Chat", text="hi"
        )
