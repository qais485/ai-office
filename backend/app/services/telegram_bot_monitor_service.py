"""Telegram Bot monitor — automatic customer-chat loop for the connected
Telegram Bot (BotFather token, Bot API).

Mirrors the Telegram Account monitor but uses plain Bot API getUpdates via
httpx (no Telethon needed):

    scheduler ("telegram_bot_monitoring", every TELEGRAM_BOT_POLL_INTERVAL s)
        └── check_all_telegram_bots()
              ├── Self-healing: ensure a TelegramBotSyncState per connected bot
              │   IntegrationAccount
              └── TelegramBotMonitorService.check_account(account_id)
                    ├── Decrypt bot token server-side (never logged)
                    ├── getUpdates(offset=durable_last_update_id + 1)
                    ├── Baseline pass: first poll acknowledges the pending
                    │   backlog (max 24h) without firing agents
                    ├── New customer messages → integration triggers for agents
                    │   mapped to THIS bot account → agent reasons (LLM) and
                    │   replies via telegram_messaging.send_message (full
                    │   security pipeline: explicit account + permissions + audit)
                    └── advance the durable offset only past processed updates

Safety rails:
    - Durable offset watermark: no replay, no loss across restarts
    - Flood cap per cycle (TELEGRAM_BOT_MAX_TRIGGERS_PER_CYCLE)
    - Per-account 60s gate, scrubbed error storage, httpx timeouts
    - The runtime pins replies to the source chat and tags them for the
      reply guard (tgbot:chat_id:message_id), so a customer is never
      double-answered
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TG_API = "https://api.telegram.org"


def _scrub_token(text: str, credentials: Dict[str, Any]) -> str:
    """Keep the bot token out of stored errors/logs."""
    safe = str(text or "")
    creds = credentials or {}
    for key in ("bot_token", "api_key"):
        secret = str(creds.get(key) or "").strip()
        if secret:
            safe = safe.replace(secret, "***")
    return safe


def _sender_label(msg: Dict[str, Any]) -> str:
    """Best-effort human label for a Bot API 'from' user object."""
    from_user = msg.get("from") or {}
    username = from_user.get("username")
    if username:
        return f"@{username}"
    first = from_user.get("first_name") or ""
    last = from_user.get("last_name") or ""
    return (f"{first} {last}").strip() or "unknown"


class TelegramBotMonitorService:
    """Per-account inbound poller for Telegram Bot (Bot API) integrations."""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # Account + state resolution
    # ------------------------------------------------------------------

    def _load_account(self, integration_account_id):
        from app.models.integration import Integration
        from app.models.integration_account import IntegrationAccount

        return (
            self.db.query(IntegrationAccount)
            .join(Integration, Integration.id == IntegrationAccount.integration_id)
            .filter(
                IntegrationAccount.id == integration_account_id,
                Integration.name == "telegram",
                IntegrationAccount.is_active == True,
                IntegrationAccount.status == "connected",
            )
            .first()
        )

    def _load_or_create_state(self, account):
        from app.models.telegram_bot_sync_state import TelegramBotSyncState

        state = (
            self.db.query(TelegramBotSyncState)
            .filter(TelegramBotSyncState.integration_account_id == account.id)
            .first()
        )
        if not state:
            state = TelegramBotSyncState(
                integration_account_id=account.id,
                user_id=account.user_id,
                is_active=True,
                last_update_id=None,
                total_processed=0,
                consecutive_errors=0,
            )
            self.db.add(state)
            self.db.commit()
            self.db.refresh(state)
        return state

    # ------------------------------------------------------------------
    # Agent resolution + trigger firing
    # ------------------------------------------------------------------

    def _linked_agents(self, account):
        """Agents explicitly mapped to THIS bot account via AgentIntegration."""
        from app.models.agent import AIAgent, LifecycleStatus
        from app.models.agent_integration import AgentIntegration
        from app.models.integration import Integration

        integration = (
            self.db.query(Integration).filter(Integration.name == "telegram").first()
        )
        if not integration:
            return []

        links = (
            self.db.query(AgentIntegration)
            .filter(
                AgentIntegration.integration_id == integration.id,
                AgentIntegration.integration_account_id == account.id,
                AgentIntegration.is_active == True,
            )
            .all()
        )

        agents = []
        for link in links:
            agent = (
                self.db.query(AIAgent)
                .filter(
                    AIAgent.id == link.agent_id,
                    AIAgent.lifecycle_status == LifecycleStatus.ACTIVE,
                )
                .first()
            )
            if agent:
                agents.append(agent)
        return agents

    def _fire_for_message(self, account, msg: Dict[str, Any]) -> int:
        from app.services.trigger_service import TriggerService

        trigger_service = TriggerService(self.db)
        event_id = f"{msg['chat_id']}:{msg['message_id']}"
        fired = 0

        for agent in self._linked_agents(account):
            try:
                trigger = trigger_service.fire_integration_trigger(
                    agent_id=agent.id,
                    integration_name="telegram",
                    event_type="telegram_bot_message_received",
                    event_id=event_id,
                    payload={
                        "message_id": msg["message_id"],
                        "chat_id": msg["chat_id"],
                        "chat_title": msg.get("chat_title", ""),
                        "sender_id": msg.get("sender_id", ""),
                        "from_address": msg.get("from_address", ""),
                        "text": msg.get("text", ""),
                        "date": msg.get("date", ""),
                        "account_id": str(account.id),
                    },
                )
                if trigger:
                    fired += 1
                    logger.info(
                        "Telegram bot message trigger created",
                        extra={
                            "agent_id": str(agent.id),
                            "trigger_id": str(trigger.id),
                            "chat_id": msg["chat_id"],
                            "message_id": msg["message_id"],
                        },
                    )
            except Exception:
                logger.error(
                    "Failed to fire Telegram bot trigger for agent",
                    extra={"agent_id": str(agent.id), "message_id": msg.get("message_id")},
                    exc_info=True,
                )
        return fired

    # ------------------------------------------------------------------
    # Account poll
    # ------------------------------------------------------------------

    async def check_account(self, integration_account_id) -> Dict[str, Any]:
        """One getUpdates cycle for one bot account."""
        from app.utils.encryption import decrypt_field

        account = self._load_account(integration_account_id)
        if not account:
            return {"skipped": "account not connected/active"}

        state = self._load_or_create_state(account)

        credentials = {
            k: decrypt_field(str(v)) for k, v in (account.credentials or {}).items()
        }
        bot_token = (
            credentials.get("bot_token")
            or credentials.get("api_key")
            or ""
        ).strip()
        if not bot_token:
            return {"skipped": "no bot token stored for this account"}

        cap = int(getattr(settings, "TELEGRAM_BOT_MAX_TRIGGERS_PER_CYCLE", 10))
        fetch_limit = int(getattr(settings, "TELEGRAM_BOT_FETCH_LIMIT", 20))
        offset = (state.last_update_id or 0) + 1

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{TG_API}/bot{bot_token}/getUpdates",
                params={"offset": offset, "limit": fetch_limit, "timeout": 0},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

        if not data.get("ok"):
            error = _scrub_token(str(data.get("description", "Unknown Bot API error")), credentials)
            state.sync_error = error[:500]
            state.consecutive_errors = (state.consecutive_errors or 0) + 1
            self.db.commit()
            return {"skipped": error}

        updates = data.get("result", [])
        max_update_id = max((int(u.get("update_id", 0)) for u in updates), default=0)

        if state.last_update_id is None:
            # Baseline pass: first poll for this bot — acknowledge everything
            # pending (up to 24h of history) WITHOUT firing agents, so old
            # messages never trigger replies.
            state.last_update_id = max_update_id
            state.last_sync_at = datetime.now(timezone.utc).isoformat()
            state.consecutive_errors = 0
            state.sync_error = None
            self.db.commit()
            return {"baselined": len(updates), "new_messages": 0}

        fired = 0
        events: List[Dict[str, Any]] = []
        acked = state.last_update_id or 0

        for update in updates:
            update_id = int(update.get("update_id", 0))
            if update_id <= acked:
                continue

            if fired >= cap:
                break  # leave the rest for the next cycle (offset not advanced)

            message = update.get("message") or update.get("edited_message")
            if not message:
                acked = update_id  # callbacks, inline queries, ... out of scope
                continue

            # Bot's own sends and bot senders never trigger replies
            from_user = message.get("from") or {}
            if from_user.get("is_bot"):
                acked = update_id
                continue

            text = str(message.get("text", "") or "").strip()
            if not text:
                acked = update_id  # media-only / service messages: nothing to answer
                continue

            chat = message.get("chat") or {}
            msg = {
                "message_id": str(message.get("message_id", "")),
                "chat_id": str(chat.get("id", "")),
                "chat_title": (chat.get("title") or chat.get("first_name") or "Private chat"),
                "sender_id": str(from_user.get("id", "")),
                "from_address": _sender_label(message),
                "text": text[:2000],
                "date": datetime.now(timezone.utc).isoformat(),
            }

            fired += self._fire_for_message(account, msg)
            acked = update_id
            events.append({
                "message_id": msg["message_id"],
                "chat_id": msg["chat_id"],
                "chat_title": msg["chat_title"],
                "sender_id": msg["sender_id"],
                "text": text[:200],
                "account_id": str(account.id),
            })

        # Acknowledge only up to the last processed update
        state.last_update_id = max(state.last_update_id or 0, acked)
        state.total_processed = (state.total_processed or 0) + fired
        state.last_sync_at = datetime.now(timezone.utc).isoformat()
        state.consecutive_errors = 0
        state.sync_error = None
        self.db.commit()

        return {"new_messages": fired, "events": events}

    def record_failure(self, integration_account_id, error: str) -> None:
        """Persist a scrubbed sync error for one bot account. Best-effort."""
        from app.models.telegram_bot_sync_state import TelegramBotSyncState

        state = (
            self.db.query(TelegramBotSyncState)
            .filter(TelegramBotSyncState.integration_account_id == integration_account_id)
            .first()
        )
        if not state:
            return
        state.consecutive_errors = (state.consecutive_errors or 0) + 1
        state.sync_error = error[:500]
        self.db.commit()


# ----------------------------------------------------------------------
# Scheduler single-pass (mirrors check_all_telegram_accounts)
# ----------------------------------------------------------------------

def _check_all_sync() -> List[Dict[str, Any]]:
    """Sync pass: self-heal bot states, poll due accounts, collect events."""
    from app.database.session import SessionLocal
    from app.database.retry import db_retry
    from app.models.integration import Integration
    from app.models.integration_account import IntegrationAccount
    from app.models.telegram_bot_sync_state import TelegramBotSyncState

    @db_retry(max_retries=2, base_delay=1.0)
    def _due_accounts(db) -> list:
        now = datetime.now(timezone.utc)
        integration = (
            db.query(Integration).filter(Integration.name == "telegram").first()
        )
        if not integration:
            return []

        accounts = (
            db.query(IntegrationAccount)
            .filter(
                IntegrationAccount.integration_id == integration.id,
                IntegrationAccount.is_active == True,
                IntegrationAccount.status == "connected",
            )
            .all()
        )

        have = {
            s.integration_account_id
            for s in db.query(TelegramBotSyncState).all()
        }
        created = False
        for account in accounts:
            if account.id in have:
                continue
            db.add(TelegramBotSyncState(
                integration_account_id=account.id,
                user_id=account.user_id,
                is_active=True,
                last_update_id=None,
                total_processed=0,
                consecutive_errors=0,
            ))
            created = True
            logger.warning(
                "Created missing TelegramBotSyncState for connected Telegram bot",
                extra={"integration_account_id": str(account.id)},
            )
        if created:
            db.commit()

        due = []
        for account in accounts:
            state = (
                db.query(TelegramBotSyncState)
                .filter(TelegramBotSyncState.integration_account_id == account.id)
                .first()
            )
            if not state or not state.is_active:
                continue
            if state.last_sync_at:
                try:
                    last = datetime.fromisoformat(state.last_sync_at)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    if (now - last).total_seconds() < 60:
                        continue
                except (ValueError, TypeError):
                    pass
            due.append(str(account.id))
        return due

    db = SessionLocal()
    try:
        account_ids = _due_accounts(db)
    finally:
        db.close()

    collected: List[Dict[str, Any]] = []
    for account_id in account_ids:
        db = SessionLocal()
        try:
            service = TelegramBotMonitorService(db)
            result = asyncio.run(service.check_account(account_id))
            if result.get("new_messages"):
                logger.info(
                    f"Telegram Bot: {result['new_messages']} new customer messages triggered",
                    extra={"integration_account_id": str(account_id)},
                )
            collected.extend(result.get("events") or [])
        except Exception as e:
            logger.error(
                f"Telegram bot check failed for account {account_id}: {e}",
                exc_info=True,
            )
            try:
                from app.utils.encryption import decrypt_field
                from app.models.integration_account import IntegrationAccount as _IA

                account = db.query(_IA).filter(_IA.id == UUID(account_id)).first()
                creds = {
                    k: decrypt_field(str(v)) for k, v in (account.credentials or {}).items()
                } if account else {}
                TelegramBotMonitorService(db).record_failure(
                    account_id, _scrub_token(str(e), creds)
                )
            except Exception:
                logger.debug("Failure bookkeeping skipped", exc_info=True)
        finally:
            db.close()

    return collected


async def check_all_telegram_bots():
    """Single Telegram Bot check pass — called by the scheduler."""
    from app.events.publisher import publish_telegram_bot_message_received

    try:
        collected = await asyncio.to_thread(_check_all_sync)
    except Exception as e:
        logger.error(f"Telegram bot monitoring error: {e}", exc_info=True)
        return

    for ev in collected:
        try:
            await publish_telegram_bot_message_received(
                message_id=ev.get("message_id", ""),
                chat_id=ev.get("chat_id", ""),
                chat_title=ev.get("chat_title", ""),
                sender_id=ev.get("sender_id", ""),
                text=ev.get("text", ""),
                account_id=ev.get("account_id") or None,
            )
        except Exception as e:
            logger.warning(f"Failed to publish Telegram bot message event: {e}")
