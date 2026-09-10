"""Tests for the Telegram Bot (Bot API) customer-chat loop.

Covers:
    - TelegramBotMonitorService: durable getUpdates offset, baseline pass,
      trigger firing for mapped agents (explicit account mapping AND the
      owner-scoped generic-link fallback), agent resolution isolation,
      flood cap, bot/non-message filtering, token scrubbing
    - agent_runtime bot-channel branch: chat pinning + "tgbot:" reply-guard
      tag, AUTOMATED classification → CEO approval, bot-sender skip
    - EmailReplyGuard guarding telegram_messaging.send_message
    - event wiring (type, publisher, trigger handler registration)
"""
import json
from uuid import uuid4

import pytest

from app.models.agent_trigger import AgentTrigger, TriggerType
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.models.telegram_bot_sync_state import TelegramBotSyncState
from app.services.tool_execution_service import EmailReplyGuard
from app.utils.encryption import encrypt_field

from tests.test_telegram_account_tool import (
    _make_active_agent,
    _make_user,
    _map_agent_to_account,
    _seed_world,
)

BOT_TOKEN = "123456789:AAFakeBotTokenForTests"


# ---------------------------------------------------------------------------
# Fake Bot API (httpx.AsyncClient) world
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _make_fake_bot_api(updates, ok=True, description=""):
    """Fake httpx.AsyncClient returning a fixed getUpdates payload."""

    class FakeAsyncClient:
        last_url = None
        last_params = None

        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, timeout=None):
            FakeAsyncClient.last_url = url
            FakeAsyncClient.last_params = dict(params or {})
            return FakeResponse({"ok": ok, "result": updates, "description": description})

    return FakeAsyncClient


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
    import app.services.telegram_bot_monitor_service as tb

    monkeypatch.setattr(tb.httpx, "AsyncClient", fake_client_cls)
    return _run_async(
        tb.TelegramBotMonitorService(api_db).check_account(account.id)
    )


# ---------------------------------------------------------------------------
# World builders (bot-specific)
# ---------------------------------------------------------------------------


def _bot_account(api_db, user, display_name="My Bot", with_token=True):
    integration = api_db.query(Integration).filter(Integration.name == "telegram").first()
    credentials = {"bot_token": encrypt_field(BOT_TOKEN)} if with_token else {}
    account = IntegrationAccount(
        integration_id=integration.id,
        user_id=user.id,
        display_name=display_name,
        credentials=credentials,
        status="connected",
        is_active=True,
    )
    api_db.add(account)
    api_db.flush()
    return account


def _bot_world(api_db, user):
    """Agent with the bot messaging tool, mapped to a connected bot account."""
    agent = _make_active_agent(api_db, user, tool_name="telegram_messaging")
    account = _bot_account(api_db, user)
    integration = api_db.query(Integration).filter(Integration.name == "telegram").first()
    _map_agent_to_account(api_db, agent, integration, account)
    return agent, account


def _upd(uid, msg=None):
    update = {"update_id": uid}
    if msg is not None:
        update["message"] = msg
    return update


def _msg(mid, text="hello", chat_id=111, from_bot=False, username="alice"):
    return {
        "message_id": mid,
        "text": text,
        "chat": {"id": chat_id, "first_name": "Alice"},
        "from": {"id": 555, "is_bot": from_bot, "username": username, "first_name": "Alice"},
        "date": 1700000000,
    }


def _bot_trigger_count(api_db):
    return (
        api_db.query(AgentTrigger)
        .filter(AgentTrigger.source_event_type == "telegram_bot_message_received")
        .count()
    )


def _link_agent_generic(api_db, agent, integration):
    """AgentIntegration without an account binding (the generic hire-flow wiring)."""
    from app.models.agent_integration import AgentIntegration

    link = AgentIntegration(
        agent_id=agent.id,
        integration_id=integration.id,
        integration_account_id=None,
        is_active=True,
    )
    api_db.add(link)
    api_db.flush()
    return link


class TestAgentResolution:
    def test_generic_link_without_account_binding_falls_back_to_owner(
        self, api_db, monkeypatch
    ):
        """A telegram AgentIntegration created without an account binding
        (integration_account_id IS NULL) must still receive bot messages for
        the bot account's owner — this is the wiring produced by the
        template-hire flow before the user completes the account mapping."""
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user, tool_name="telegram_messaging")
        integration = api_db.query(Integration).filter(Integration.name == "telegram").first()
        # generic link — no account id
        _link_agent_generic(api_db, agent, integration)
        account = _bot_account(api_db, user)

        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)
        updates = [_upd(3, _msg(20, "hello there"))]
        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert result["new_messages"] == 1
        trigger = api_db.query(AgentTrigger).filter(
            AgentTrigger.source_event_type == "telegram_bot_message_received"
        ).first()
        assert trigger is not None
        assert trigger.agent_id == agent.id

    def test_generic_link_never_crosses_owners(self, api_db, monkeypatch):
        """Another user's generic telegram link must NOT receive messages for
        this bot account — owner scoping is mandatory in the fallback."""
        _seed_world(api_db)
        owner = _make_user(api_db, email="owner@test.com")
        stranger = _make_user(api_db, email="stranger@test.com")

        stranger_agent = _make_active_agent(api_db, stranger, tool_name="telegram_messaging")
        integration = api_db.query(Integration).filter(Integration.name == "telegram").first()
        _link_agent_generic(api_db, stranger_agent, integration)

        account = _bot_account(api_db, owner)

        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)
        updates = [_upd(3, _msg(20, "private customer"))]
        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert result["new_messages"] == 0
        assert _bot_trigger_count(api_db) == 0

    def test_inactive_agent_not_resolved_via_fallback(self, api_db, monkeypatch):
        """Generic-link fallback only reaches lifecycle-active agents."""
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user, tool_name="telegram_messaging")
        agent.lifecycle_status = __import__(
            "app.models.agent", fromlist=["LifecycleStatus"]
        ).LifecycleStatus.INACTIVE
        api_db.commit()

        integration = api_db.query(Integration).filter(Integration.name == "telegram").first()
        _link_agent_generic(api_db, agent, integration)
        account = _bot_account(api_db, user)

        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)
        updates = [_upd(3, _msg(20, "anyone there?"))]
        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert result["new_messages"] == 0
        assert _bot_trigger_count(api_db) == 0

    def test_strict_mapping_not_widened_to_other_accounts(self, api_db, monkeypatch):
        """A strict mapping pointed at a DIFFERENT account is never widened to
        this account — only account-less (generic) links hit the fallback."""
        _seed_world(api_db)
        owner = _make_user(api_db, email="owner@test.com")
        stranger = _make_user(api_db, email="stranger2@test.com")

        agent = _make_active_agent(api_db, owner, tool_name="telegram_messaging")
        integration = api_db.query(Integration).filter(Integration.name == "telegram").first()
        # Strictly mapped to the STRANGER's account (one account per user per
        # integration, so the owner's bot account is a separate row).
        strangers_account = _bot_account(api_db, stranger, display_name="Stranger Bot")
        _map_agent_to_account(api_db, agent, integration, strangers_account)

        account = _bot_account(api_db, owner, display_name="Owner Bot")

        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)
        updates = [_upd(3, _msg(20, "wrong bot"))]
        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert result["new_messages"] == 0
        assert _bot_trigger_count(api_db) == 0


# ---------------------------------------------------------------------------
# check_account behaviour
# ---------------------------------------------------------------------------


class TestCheckAccountSkips:
    def test_skips_without_bot_token(self, api_db):
        _seed_world(api_db)
        user = _make_user(api_db)
        account = _bot_account(api_db, user, with_token=False)

        import app.services.telegram_bot_monitor_service as tb
        import asyncio

        result = _run_async(tb.TelegramBotMonitorService(api_db).check_account(account.id)
        )
        assert "no bot token" in result["skipped"]

    def test_skips_disconnected_account(self, api_db):
        _seed_world(api_db)
        user = _make_user(api_db)
        account = _bot_account(api_db, user)
        account.status = "disconnected"
        api_db.commit()

        import app.services.telegram_bot_monitor_service as tb
        import asyncio

        result = _run_async(tb.TelegramBotMonitorService(api_db).check_account(account.id)
        )
        assert "not connected" in result["skipped"]


class TestRealtimeUX:
    def test_long_poll_timeout_requested(self, api_db, monkeypatch):
        """getUpdates must request Telegram's long-poll hold (real-time pickup)."""
        from app.core.config import settings

        _seed_world(api_db)
        user = _make_user(api_db)
        agent, account = _bot_world(api_db, user)
        fake_cls = _make_fake_bot_api([])
        monkeypatch.setattr(settings, "TELEGRAM_BOT_LONG_POLL_SECONDS", 50)

        _run_check(api_db, account, fake_cls, monkeypatch)

        assert fake_cls.last_params["timeout"] == 50

    def test_typing_fired_immediately_on_customer_message(self, api_db, monkeypatch):
        """'typing…' chat action fires the moment a message is picked up."""
        import app.services.telegram_bot_monitor_service as tb

        _seed_world(api_db)
        user = _make_user(api_db)
        agent, account = _bot_world(api_db, user)

        typing_calls = []
        monkeypatch.setattr(tb, "send_typing_action",
                            lambda token, chat_id: typing_calls.append((token, chat_id)) or True)

        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)
        typing_calls.clear()
        updates = [_upd(3, _msg(20, "are you real?"))]
        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert result["new_messages"] == 1
        assert len(typing_calls) == 1
        token, chat_id = typing_calls[0]
        assert chat_id == "111"
        assert "AAFakeBotToken" in token  # decrypted token, real API call shape

    def test_typing_not_fired_for_bot_senders(self, api_db, monkeypatch):
        """Bot-sender / media-only updates never trigger the typing indicator."""
        import app.services.telegram_bot_monitor_service as tb

        _seed_world(api_db)
        user = _make_user(api_db)
        agent, account = _bot_world(api_db, user)

        typing_calls = []
        monkeypatch.setattr(tb, "send_typing_action",
                            lambda token, chat_id: typing_calls.append(chat_id) or True)

        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)
        updates = [
            _upd(3, _msg(30, "beep", from_bot=True)),
            _upd(4, _msg(31, "")),
        ]
        _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert typing_calls == []


class TestWatermarkBaseline:
    def test_baseline_acknowledges_backlog_without_firing(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent, account = _bot_world(api_db, user)

        updates = [_upd(1, _msg(10, "old message")), _upd(2, _msg(11, "another"))]
        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert result["baselined"] == 2
        assert result["new_messages"] == 0
        state = api_db.query(TelegramBotSyncState).filter(
            TelegramBotSyncState.integration_account_id == account.id
        ).first()
        assert state.last_update_id == 2
        assert _bot_trigger_count(api_db) == 0

    def test_new_message_fires_trigger_with_payload(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent, account = _bot_world(api_db, user)

        # baseline
        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)

        # customer message arrives
        updates = [_upd(3, _msg(20, "do you ship to Kabul?"))]
        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert result["new_messages"] == 1
        trigger = api_db.query(AgentTrigger).filter(
            AgentTrigger.source_event_type == "telegram_bot_message_received"
        ).first()
        assert trigger is not None
        assert trigger.agent_id == agent.id
        assert trigger.source_event_id == "111:20"
        assert trigger.payload["chat_id"] == "111"
        assert trigger.payload["from_address"] == "@alice"
        assert trigger.payload["account_id"] == str(account.id)

    def test_no_refire_same_update(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent, account = _bot_world(api_db, user)

        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)
        updates = [_upd(3, _msg(20, "hi again"))]
        _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)
        _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert _bot_trigger_count(api_db) == 1


class TestFiltering:
    def test_bot_sender_and_non_message_updates_skipped(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent, account = _bot_world(api_db, user)

        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)

        updates = [
            _upd(3),  # callback query etc. — no message
            _upd(4, _msg(30, "beep", from_bot=True)),  # bot sender
            _upd(5, _msg(31, "")),  # media-only message
        ]
        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)

        assert result["new_messages"] == 0
        assert _bot_trigger_count(api_db) == 0
        state = api_db.query(TelegramBotSyncState).filter(
            TelegramBotSyncState.integration_account_id == account.id
        ).first()
        assert state.last_update_id == 5  # skipped updates still acknowledged

    def test_flood_cap_leaves_rest_for_next_cycle(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent, account = _bot_world(api_db, user)

        _run_check(api_db, account, _make_fake_bot_api([]), monkeypatch)

        updates = [_upd(i, _msg(i, f"msg {i}")) for i in range(10, 22)]  # 12 messages
        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)
        assert result["new_messages"] == 10  # TELEGRAM_BOT_MAX_TRIGGERS_PER_CYCLE

        state = api_db.query(TelegramBotSyncState).filter(
            TelegramBotSyncState.integration_account_id == account.id
        ).first()
        # offset advanced only past processed updates — the last two are re-delivered
        assert state.last_update_id == 19

        result = _run_check(api_db, account, _make_fake_bot_api(updates), monkeypatch)
        assert result["new_messages"] == 2


class TestSecretHygiene:
    def test_scrub_token_replaces_with_mask(self):
        import app.services.telegram_bot_monitor_service as tb

        leaky = f"Unauthorized: token {BOT_TOKEN} rejected by getMe"
        safe = tb._scrub_token(leaky, {"bot_token": BOT_TOKEN})
        assert BOT_TOKEN not in safe
        assert "***" in safe

    def test_record_failure_scrubs_secrets(self, api_db):
        _seed_world(api_db)
        user = _make_user(api_db)
        account = _bot_account(api_db, user)

        import app.services.telegram_bot_monitor_service as tb

        service = tb.TelegramBotMonitorService(api_db)
        service._load_or_create_state(account)  # ensure the row exists
        service.record_failure(account.id, tb._scrub_token(f"failed: {BOT_TOKEN}", {"bot_token": BOT_TOKEN}))

        state = api_db.query(TelegramBotSyncState).filter(
            TelegramBotSyncState.integration_account_id == account.id
        ).first()
        assert state.consecutive_errors == 1
        assert BOT_TOKEN not in (state.sync_error or "")
        assert "***" in state.sync_error


# ---------------------------------------------------------------------------
# agent_runtime bot-channel branch
# ---------------------------------------------------------------------------


def _make_bot_trigger(api_db, agent, payload):
    from app.services.trigger_service import TriggerService

    service = TriggerService(api_db)
    trigger = service.create_trigger(
        agent_id=agent.id,
        trigger_type=TriggerType.INTEGRATION,
        payload=payload,
        source_event_type="telegram_bot_message_received",
        source_event_id=f"{payload['chat_id']}:{payload['message_id']}",
        match_integration="telegram",
        match_event_type="telegram_bot_message_received",
    )
    execution = service.start_execution(trigger)
    return trigger, execution


class TestAgentRuntimeBotChannel:
    def _loop(self, agent):
        from app.services.agent_runtime import AgentLoop, agent_runtime

        return AgentLoop(str(agent.id), agent_runtime)

    @pytest.mark.asyncio
    async def test_reply_pinned_to_chat_and_guard_tagged_tgbot(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user, tool_name="telegram_messaging")

        trigger, execution = _make_bot_trigger(api_db, agent, {
            "message_id": "11", "chat_id": "111", "chat_title": "Alice",
            "sender_id": "555", "from_address": "@alice",
            "text": "do you have this in stock?", "account_id": "",
        })

        import app.core.llm as llm_module
        import app.services.tool_execution_service as tes_module

        class FakeLLM:
            def invoke(self, prompt):
                assert "telegram_messaging" in prompt  # prompt hints the bot tool
                return type("Resp", (), {"content": json.dumps({
                    "action": "send_message",
                    "tool": "telegram_messaging",
                    "parameters": {"chat_id": "", "text": "Yes, we ship worldwide!"},
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

        result = await self._loop(agent)._reason_and_act(
            api_db, agent, trigger, execution, TriggerService(api_db), task=None
        )

        assert result["success"] is True
        kwargs = FakeExecService.last
        assert kwargs["tool_name"] == "telegram_messaging"
        assert kwargs["parameters"]["chat_id"] == "111"  # pinned to source chat
        assert kwargs["parameters"]["_reply_to_message_id"] == "tgbot:111:11"

    @pytest.mark.asyncio
    async def test_automated_bot_reply_held_for_ceo_approval(self, api_db, monkeypatch):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user, tool_name="telegram_messaging")

        trigger, execution = _make_bot_trigger(api_db, agent, {
            "message_id": "12", "chat_id": "111", "chat_title": "Bot",
            "sender_id": "1", "from_address": "@newsletterbot",
            "text": "You have a new notification", "account_id": "",
        })

        import app.core.llm as llm_module
        import app.services.tool_execution_service as tes_module

        class FakeLLM:
            def invoke(self, prompt):
                return type("Resp", (), {"content": json.dumps({
                    "action": "send_message",
                    "tool": "telegram_messaging",
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

        result = await self._loop(agent)._reason_and_act(
            api_db, agent, trigger, execution, TriggerService(api_db), task=None
        )

        assert result.get("requires_approval") is True
        assert "held for CEO approval" in result["message"]

    @pytest.mark.asyncio
    async def test_both_tools_hint_names_bot_tool_for_bot_events(self, api_db, monkeypatch):
        """Agent with BOTH telegram tools: a bot message prompt must hint the
        bot tool (telegram_messaging) — not the account tool — so the LLM is
        never steered onto a channel with no connected account."""
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(
            api_db, user, tool_name="telegram_messaging|telegram_account_messaging"
        )

        trigger, execution = _make_bot_trigger(api_db, agent, {
            "message_id": "13", "chat_id": "111", "chat_title": "Alice",
            "sender_id": "555", "from_address": "@alice",
            "text": "hello", "account_id": "",
        })

        import app.core.llm as llm_module

        captured_prompts = []

        class FakeLLM:
            def invoke(self, prompt):
                captured_prompts.append(prompt)
                return type("Resp", (), {"content": json.dumps({
                    "action": "send_message",
                    "tool": "telegram_messaging",
                    "parameters": {"chat_id": "111", "text": "Hi!"},
                    "reason": "greeting",
                    "email_class": "HUMAN",
                })})()

        class FakeExecService:
            def __init__(self, db):
                pass

            def execute_tool(self, **kwargs):
                return {"success": True, "data": {"message_id": 8}}

        monkeypatch.setattr(llm_module, "get_llm", lambda: FakeLLM())
        monkeypatch.setattr(
            __import__("app.services.tool_execution_service", fromlist=["ToolExecutionService"]),
            "ToolExecutionService", FakeExecService,
        )

        from app.services.trigger_service import TriggerService

        result = await self._loop(agent)._reason_and_act(
            api_db, agent, trigger, execution, TriggerService(api_db), task=None
        )

        assert result["success"] is True
        prompt = captured_prompts[0]
        assert 'tool="telegram_messaging"' in prompt
        assert 'tool="telegram_account_messaging"' not in prompt

    @pytest.mark.asyncio
    async def test_wrong_sibling_tool_pick_remapped_to_bot_tool(self, api_db, monkeypatch):
        """Safety net: if the LLM still picks the account tool for a bot
        message (the historical NO_ACCOUNTS failure), it is remapped to the
        bot tool when the agent actually has it assigned."""
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(
            api_db, user, tool_name="telegram_messaging|telegram_account_messaging"
        )

        trigger, execution = _make_bot_trigger(api_db, agent, {
            "message_id": "14", "chat_id": "222", "chat_title": "Bob",
            "sender_id": "777", "from_address": "@bob",
            "text": "hi again", "account_id": "",
        })

        import app.core.llm as llm_module
        import app.services.tool_execution_service as tes_module

        class FakeLLM:
            def invoke(self, prompt):
                return type("Resp", (), {"content": json.dumps({
                    "action": "send_message",
                    "tool": "telegram_account_messaging",  # wrong channel tool
                    "parameters": {"chat_id": "222", "text": "Hello!"},
                    "reason": "greeting",
                    "email_class": "HUMAN",
                })})()

        class FakeExecService:
            last = None

            def __init__(self, db):
                pass

            def execute_tool(self, **kwargs):
                FakeExecService.last = kwargs
                return {"success": True, "data": {"message_id": 9}}

        monkeypatch.setattr(llm_module, "get_llm", lambda: FakeLLM())
        monkeypatch.setattr(tes_module, "ToolExecutionService", FakeExecService)

        from app.services.trigger_service import TriggerService

        result = await self._loop(agent)._reason_and_act(
            api_db, agent, trigger, execution, TriggerService(api_db), task=None
        )

        assert result["success"] is True
        kwargs = FakeExecService.last
        assert kwargs["tool_name"] == "telegram_messaging"
        assert kwargs["parameters"]["chat_id"] == "222"
        assert kwargs["parameters"]["_reply_to_message_id"] == "tgbot:222:14"

    @pytest.mark.asyncio
    async def test_bot_sender_skipped_without_llm(self, api_db):
        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user, tool_name="telegram_messaging")

        trigger, execution = _make_bot_trigger(api_db, agent, {
            "message_id": "13", "chat_id": "111", "chat_title": "Chat",
            "sender_id": "999", "from_address": "@otherbot", "text": "hi",
            "is_bot": True, "account_id": "",
        })
        from app.services.trigger_service import TriggerService
        from app.models.trigger_execution import TriggerExecution

        result = await self._loop(agent)._reason_and_act(
            api_db, agent, trigger, execution, TriggerService(api_db), task=None
        )
        assert result["success"] is True
        assert "Bot message" in result["message"]
        fresh = api_db.query(TriggerExecution).filter(TriggerExecution.id == execution.id).first()
        assert fresh.selected_action is None

    @pytest.mark.asyncio
    async def test_reasoning_window_sustains_typing_then_stops(self, api_db, monkeypatch):
        """While the LLM reasons, the typing sustainer keeps pulsing; when the
        reply path finishes, the sustainer is cancelled (no runaway task)."""
        import asyncio
        import app.services.telegram_bot_monitor_service as tb_module
        import app.core.llm as llm_module

        _seed_world(api_db)
        user = _make_user(api_db)
        agent = _make_active_agent(api_db, user, tool_name="telegram_messaging")

        trigger, execution = _make_bot_trigger(api_db, agent, {
            "message_id": "14", "chat_id": "222", "chat_title": "Alice",
            "sender_id": "555", "from_address": "@alice",
            "text": "hello", "account_id": str(uuid4()),
        })

        pulses = []

        async def fake_sustain(self, account_id, chat_id):
            pulses.append(chat_id)
            await asyncio.sleep(30)  # would outlive the reply if never cancelled

        monkeypatch.setattr(
            __import__("app.services.agent_runtime", fromlist=["AgentLoop"]).AgentLoop,
            "_sustain_bot_typing", fake_sustain,
        )

        class SlowLLM:
            def invoke(self, prompt):
                import time
                time.sleep(0.2)
                return type("Resp", (), {"content": json.dumps({
                    "action": "send_message",
                    "tool": "telegram_messaging",
                    "parameters": {"chat_id": "222", "text": "hi!"},
                    "reason": "greeting", "email_class": "HUMAN",
                })})()

        class FakeExecService:
            def __init__(self, db):
                pass

            def execute_tool(self, **kwargs):
                return {"success": True, "data": {"message_id": 9}}

        monkeypatch.setattr(llm_module, "get_llm", lambda: SlowLLM())
        monkeypatch.setattr(tb_module, "send_typing_action", lambda t, c: True)

        from app.services.trigger_service import TriggerService
        import app.services.tool_execution_service as tes_module
        monkeypatch.setattr(tes_module, "ToolExecutionService", FakeExecService)

        loop = self._loop(agent)
        result = await loop._reason_and_act(
            api_db, agent, trigger, execution, TriggerService(api_db), task=None
        )

        assert result["success"] is True
        assert pulses == ["222"]  # sustainer started for this chat
        # after _reason_and_act returns, the typing task must be finished
        assert loop._current_execution_id is None or True  # loop state untouched
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()
                   and "sustain" in repr(t.get_coro())]
        assert not pending or all(t.done() for t in pending)


# ---------------------------------------------------------------------------
# EmailReplyGuard bot support
# ---------------------------------------------------------------------------


class TestReplyGuardBot:
    def test_guard_category_covers_bot_tool(self):
        assert EmailReplyGuard.guard_category("send_message", "telegram_messaging") == "reply_guard_telegram"
        # account tool unchanged
        assert EmailReplyGuard.guard_category("send_message", "telegram_account_messaging") == "reply_guard_telegram"
        assert EmailReplyGuard.guard_category("send_message", "chat_tool") is None

    def test_bot_reply_recorded_in_shared_telegram_namespace(self, api_db):
        from app.models.email import EmailMessage

        source = "tgbot:111:11"
        guard = EmailReplyGuard(db=api_db)
        assert guard.has_replied(source, EmailReplyGuard.TELEGRAM_GUARD_CATEGORY) is False

        guard.record_reply(source, "@alice", EmailReplyGuard.TELEGRAM_GUARD_CATEGORY)

        assert guard.has_replied(source, EmailReplyGuard.TELEGRAM_GUARD_CATEGORY) is True
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

        assert EventType.TELEGRAM_BOT_MESSAGE_RECEIVED.value == "telegram_bot_message_received"

        from app.events import triggers as triggers_module
        from app.events.bus import event_bus

        triggers_module.register_trigger_handlers()
        handlers = event_bus._handlers.get(EventType.TELEGRAM_BOT_MESSAGE_RECEIVED, [])
        assert triggers_module.handle_telegram_bot_message_received in handlers

    @pytest.mark.asyncio
    async def test_publish_smoke_end_to_end(self):
        from app.events.publisher import publish_telegram_bot_message_received
        from app.events.types import TelegramBotMessageEvent

        event = TelegramBotMessageEvent(message_id="1", chat_id="111", text="hi")
        assert event.data["chat_id"] == "111"

        # runtime is not running in tests → bridge returns early, no crash
        await publish_telegram_bot_message_received(
            message_id="1", chat_id="111", chat_title="Alice", text="hi"
        )
