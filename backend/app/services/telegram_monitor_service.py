"""Telegram Account monitor — automatic inbound loop for connected Telegram
user accounts (MTProto).

Mirrors the Gmail monitoring architecture:

    scheduler ("telegram_monitoring", every TELEGRAM_POLL_INTERVAL seconds)
        └── check_all_telegram_accounts()
              ├── Self-healing: ensure a TelegramSyncState row exists for every
              │   connected telegram_account IntegrationAccount
              └── TelegramMonitorService.check_account(account_id)
                    ├── Decrypt credentials server-side (session stays local)
                    ├── Telethon: fetch recent incoming messages per dialog
                    ├── Baseline pass: the first time a dialog is seen only its
                    │   watermark is recorded — old history never auto-replies
                    ├── New incoming messages → fire integration triggers so
                    │   linked agents reason and reply via the
                    │   telegram_account_messaging tool (same security pipeline:
                    │   explicit account mapping + permissions + audit)
                    └── collect TelegramMessageEvent dicts for the live feed

Safety rails:
    - Only *private user chats* by default (TELEGRAM_WATCH_GROUPS=False);
      bots and bot senders are always skipped (no bot-to-bot loops)
    - Outgoing / service / media-only messages are never processed
    - Per-account 60s gate, flood cap per cycle, watermark dedup, capped
      processed-marker list — plus the last-line send guard in
      ToolExecutionService (_reply_to_message_id → reply_guard_telegram)
    - API Hash / session never appear in logs or sync errors (scrubbed)
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.config import settings

logger = logging.getLogger(__name__)

# Bounded processed-marker list (restart safety net beyond watermarks)
PROCESSED_IDS_CAP = 500


def _load_telethon():
    """Lazily import Telethon; returns (TelegramClient, StringSession) or (None, None)."""
    try:
        from telethon import TelegramClient  # type: ignore
        from telethon.sessions import StringSession  # type: ignore
        return TelegramClient, StringSession
    except ImportError:
        return None, None


def _scrub_secrets(text: str, credentials: Dict[str, Any]) -> str:
    """Keep the API Hash and session string out of stored errors/logs."""
    from app.services.integration_providers.telegram_account import (
        TelegramAccountProvider,
    )

    return TelegramAccountProvider._scrub_secrets(str(text or ""), credentials)


def _sender_label(entity: Any) -> str:
    """Best-effort human label for a Telegram user entity."""
    username = getattr(entity, "username", None)
    if username:
        return f"@{username}"
    first = getattr(entity, "first_name", None) or ""
    last = getattr(entity, "last_name", None) or ""
    return (f"{first} {last}").strip() or "unknown"


class TelegramMonitorService:
    """Per-account inbound poller for Telegram Account (MTProto) integrations."""

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
                Integration.name == "telegram_account",
                IntegrationAccount.is_active == True,
                IntegrationAccount.status == "connected",
            )
            .first()
        )

    def _load_or_create_state(self, account):
        from app.models.telegram_sync_state import TelegramSyncState

        state = (
            self.db.query(TelegramSyncState)
            .filter(TelegramSyncState.integration_account_id == account.id)
            .first()
        )
        if not state:
            state = TelegramSyncState(
                integration_account_id=account.id,
                user_id=account.user_id,
                is_active=True,
                last_seen_message_ids={},
                processed_message_ids=[],
                total_processed=0,
                consecutive_errors=0,
            )
            self.db.add(state)
            self.db.commit()
            self.db.refresh(state)
        return state

    # ------------------------------------------------------------------
    # Trigger firing
    # ------------------------------------------------------------------

    def _linked_agents(self, account):
        """Agents explicitly mapped to THIS account via AgentIntegration."""
        from app.models.agent import AIAgent, LifecycleStatus
        from app.models.agent_integration import AgentIntegration
        from app.models.integration import Integration

        integration = (
            self.db.query(Integration).filter(Integration.name == "telegram_account").first()
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
        """Fire integration triggers for every agent mapped to this account."""
        from app.services.trigger_service import TriggerService

        trigger_service = TriggerService(self.db)
        event_id = f"{msg['chat_id']}:{msg['message_id']}"
        fired = 0

        for agent in self._linked_agents(account):
            try:
                trigger = trigger_service.fire_integration_trigger(
                    agent_id=agent.id,
                    integration_name="telegram_account",
                    event_type="telegram_message_received",
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
                        "Telegram message trigger created",
                        extra={
                            "agent_id": str(agent.id),
                            "trigger_id": str(trigger.id),
                            "chat_id": msg["chat_id"],
                            "message_id": msg["message_id"],
                        },
                    )
            except Exception as e:
                logger.error(
                    "Failed to fire Telegram trigger for agent",
                    extra={"agent_id": str(agent.id), "message_id": msg.get("message_id")},
                    exc_info=True,
                )
        return fired

    # ------------------------------------------------------------------
    # Account poll
    # ------------------------------------------------------------------

    async def check_account(self, integration_account_id) -> Dict[str, Any]:
        """One poll cycle for one account. Returns counts + collected events."""
        from app.utils.encryption import decrypt_field

        account = self._load_account(integration_account_id)
        if not account:
            return {"skipped": "account not connected/active"}

        state = self._load_or_create_state(account)
        last_seen: Dict[str, int] = dict(state.last_seen_message_ids or {})
        processed: List[str] = list(state.processed_message_ids or [])
        processed_set = set(processed)

        credentials = {
            k: decrypt_field(str(v)) for k, v in (account.credentials or {}).items()
        }
        api_id = str(credentials.get("api_id") or "").strip()
        api_hash = str(credentials.get("api_hash") or "").strip()
        session_string = str(credentials.get("session") or "").strip()

        if not session_string:
            return {"skipped": "no MTProto session bound (complete the Telegram login first)"}

        TelegramClient, StringSession = _load_telethon()
        if not TelegramClient:
            return {"skipped": "telethon is not installed on the server"}

        events: List[Dict[str, Any]] = []
        fired = 0
        cap = int(getattr(settings, "TELEGRAM_MAX_TRIGGERS_PER_CYCLE", 10))
        watch_groups = bool(getattr(settings, "TELEGRAM_WATCH_GROUPS", False))
        fetch_limit = int(getattr(settings, "TELEGRAM_FETCH_LIMIT", 20))

        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                state.sync_error = _scrub_secrets(
                    "Stored session is not authorized anymore", credentials
                )[:500]
                state.consecutive_errors = (state.consecutive_errors or 0) + 1
                self.db.commit()
                return {"skipped": "session not authorized"}

            async for dialog in client.iter_dialogs():
                # Private user chats by default; groups/channels opt-in only
                if not watch_groups and not dialog.is_user:
                    continue
                entity = getattr(dialog, "entity", None)
                if entity is None:
                    continue
                if getattr(entity, "bot", False):
                    continue  # never converse with bots

                messages = await client.get_messages(dialog.entity, limit=fetch_limit)
                if not messages:
                    continue

                incoming = [
                    m for m in messages
                    if not getattr(m, "out", False)
                    and getattr(m, "action", None) is None
                    and str(getattr(m, "message", "") or "").strip()
                ]
                if not incoming:
                    continue

                dialog_key = str(dialog.id)
                seen = last_seen.get(dialog_key)

                if seen is None:
                    # Baseline: record the newest incoming id, fire nothing.
                    last_seen[dialog_key] = max(m.id for m in incoming)
                    continue

                fresh = sorted((m for m in incoming if m.id > seen), key=lambda m: m.id)
                advanced = seen
                for m in fresh:
                    marker = f"{dialog.id}:{m.id}"
                    if marker in processed_set:
                        advanced = m.id
                        continue
                    if fired >= cap:
                        break  # leave the rest for the next cycle

                    text = str(m.message or "").strip()
                    msg = {
                        "message_id": str(m.id),
                        "chat_id": dialog_key,
                        "chat_title": (getattr(dialog, "name", "") or "").strip() or "Private chat",
                        "sender_id": str(m.sender_id or ""),
                        "from_address": _sender_label(entity),
                        "text": text[:2000],
                        "date": m.date.isoformat() if getattr(m, "date", None) else "",
                    }

                    fired += self._fire_for_message(account, msg)
                    processed.append(marker)
                    processed_set.add(marker)
                    advanced = m.id

                    events.append({
                        "message_id": msg["message_id"],
                        "chat_id": msg["chat_id"],
                        "chat_title": msg["chat_title"],
                        "sender_id": msg["sender_id"],
                        "text": text[:200],
                        "account_id": str(account.id),
                    })

                if advanced > seen:
                    last_seen[dialog_key] = advanced
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

        # Persist watermarks + markers (bounded), bookkeeping
        state.last_seen_message_ids = last_seen
        state.processed_message_ids = processed[-PROCESSED_IDS_CAP:]
        state.total_processed = (state.total_processed or 0) + fired
        state.last_sync_at = datetime.now(timezone.utc).isoformat()
        state.consecutive_errors = 0
        state.sync_error = None
        self.db.commit()

        return {
            "new_messages": fired,
            "dialogs": len(last_seen),
            "events": events,
        }

    def record_failure(self, integration_account_id, error: str) -> None:
        """Persist a scrubbed sync error for one account's state. Best-effort."""
        from app.models.telegram_sync_state import TelegramSyncState

        state = (
            self.db.query(TelegramSyncState)
            .filter(TelegramSyncState.integration_account_id == integration_account_id)
            .first()
        )
        if not state:
            return
        state.consecutive_errors = (state.consecutive_errors or 0) + 1
        state.sync_error = error[:500]
        self.db.commit()


# ----------------------------------------------------------------------
# Scheduler single-pass (mirrors check_all_gmail_accounts)
# ----------------------------------------------------------------------

def _check_all_sync() -> List[Dict[str, Any]]:
    """Sync pass: self-heal states, return event dicts collected from due accounts."""
    from app.database.session import SessionLocal
    from app.database.retry import db_retry
    from app.models.integration import Integration
    from app.models.integration_account import IntegrationAccount
    from app.models.telegram_sync_state import TelegramSyncState

    @db_retry(max_retries=2, base_delay=1.0)
    def _due_accounts(db) -> list:
        now = datetime.now(timezone.utc)
        integration = (
            db.query(Integration).filter(Integration.name == "telegram_account").first()
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

        # Self-healing: every connected account must have a sync state
        have = {
            s.integration_account_id
            for s in db.query(TelegramSyncState).all()
        }
        created = False
        for account in accounts:
            if account.id in have:
                continue
            db.add(TelegramSyncState(
                integration_account_id=account.id,
                user_id=account.user_id,
                is_active=True,
                last_seen_message_ids={},
                processed_message_ids=[],
                total_processed=0,
                consecutive_errors=0,
            ))
            created = True
            logger.warning(
                "Created missing TelegramSyncState for connected Telegram account",
                extra={"integration_account_id": str(account.id)},
            )
        if created:
            db.commit()

        due = []
        for account in accounts:
            state = (
                db.query(TelegramSyncState)
                .filter(TelegramSyncState.integration_account_id == account.id)
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
    collected: List[Dict[str, Any]] = []
    try:
        account_ids = _due_accounts(db)
    finally:
        db.close()

    for account_id in account_ids:
        db = SessionLocal()
        try:
            service = TelegramMonitorService(db)
            result = asyncio.run(service.check_account(account_id))
            if result.get("new_messages"):
                logger.info(
                    f"Telegram: {result['new_messages']} new messages triggered",
                    extra={"integration_account_id": str(account_id)},
                )
            collected.extend(result.get("events") or [])
        except Exception as e:
            logger.error(
                f"Telegram check failed for account {account_id}: {e}",
                exc_info=True,
            )
            _record_failure_safe(db, account_id, e)
        finally:
            db.close()

    return collected


def _record_failure_safe(db, account_id: str, error: Exception) -> None:
    """Best-effort failure bookkeeping with secret scrubbing."""
    try:
        from app.models.integration_account import IntegrationAccount
        from uuid import UUID

        account = db.query(IntegrationAccount).filter(
            IntegrationAccount.id == UUID(account_id)
        ).first()
        creds = account.credentials if account else {}
        TelegramMonitorService(db).record_failure(account_id, _scrub_secrets(str(error), creds or {}))
    except Exception:
        logger.debug("Failure bookkeeping skipped", exc_info=True)


async def check_all_telegram_accounts():
    """Single Telegram check pass — called by the scheduler."""
    from app.events.publisher import publish_telegram_message_received

    try:
        collected = await asyncio.to_thread(_check_all_sync)
    except Exception as e:
        logger.error(f"Telegram monitoring error: {e}", exc_info=True)
        return

    # Live-feed events are published on the main event loop (websocket-safe)
    for ev in collected:
        try:
            await publish_telegram_message_received(
                message_id=ev.get("message_id", ""),
                chat_id=ev.get("chat_id", ""),
                chat_title=ev.get("chat_title", ""),
                sender_id=ev.get("sender_id", ""),
                text=ev.get("text", ""),
                account_id=ev.get("account_id") or None,
            )
        except Exception as e:
            logger.warning(f"Failed to publish Telegram message event: {e}")
