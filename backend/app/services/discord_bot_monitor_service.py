"""Discord Bot monitor — automatic customer-chat loop for the connected
Discord Bot (Developer Portal token, Bot REST API).

Mirrors the Telegram Bot monitor but polls Discord's REST API — Discord has
no getUpdates-style offset, so the durable watermark is the highest
acknowledged message id (snowflake) per channel, stored as a JSON mapping:

    scheduler ("discord_monitoring", every DISCORD_BOT_POLL_INTERVAL s)
        └── check_all_discord_bots()
              ├── Self-healing: ensure a DiscordBotSyncState per connected bot
              │   IntegrationAccount
              └── DiscordBotMonitorService.check_account(account_id)
                    ├── Decrypt bot token server-side (never logged)
                    ├── GET /users/@me/channels (DM channels the bot can see)
                    ├── For each channel: fetch messages AFTER the durable
                    │   watermark, newest → oldest
                    ├── Baseline pass: first poll acknowledges existing
                    │   messages WITHOUT firing agents
                    ├── New customer messages → integration triggers for
                    │   agents mapped to THIS bot account → agent reasons
                    │   (LLM) and replies via discord_messaging.send_message
                    │   (full security pipeline: explicit account +
                    │   permissions + audit)
                    └── advance the per-channel watermark only past
                        processed messages

Safety rails:
    - Durable per-channel watermark: no replay, no loss across restarts
    - Flood cap per cycle (DISCORD_BOT_MAX_TRIGGERS_PER_CYCLE)
    - Bot/own-message filtering (no bot-to-bot loops)
    - Per-account gate, scrubbed error storage, httpx timeouts
    - The runtime pins replies to the source channel and tags them for the
      reply guard (discord:channel_id:message_id), so a customer is never
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

DC_API = "https://discord.com/api/v10"


def _scrub_token(text: str, credentials: Dict[str, Any]) -> str:
    """Keep the bot token out of stored errors/logs."""
    safe = str(text or "")
    creds = credentials or {}
    for key in ("bot_token", "api_key"):
        secret = str(creds.get(key) or "").strip()
        if secret:
            safe = safe.replace(secret, "***")
    return safe


def _headers(bot_token: str) -> Dict[str, str]:
    return {"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}


def send_typing_action(bot_token: str, channel_id: str) -> bool:
    """Fire a 'typing…' indicator trigger (sync, best-effort).

    Discord's typing indicator lasts ~8s per trigger; the reply path
    re-fires it every 4.5s while the agent reasons.
    """
    token = str(bot_token or "").strip()
    channel = str(channel_id or "").strip()
    if not token or not channel:
        return False
    try:
        resp = httpx.post(
            f"{DC_API}/channels/{channel}/typing",
            headers=_headers(token),
            timeout=5,
        )
        return resp.status_code in (200, 204)
    except Exception:
        logger.debug("Discord typing indicator failed", exc_info=True)
        return False


class DiscordBotMonitorService:
    """Per-account inbound poller for Discord Bot integrations."""

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
                Integration.name == "discord",
                IntegrationAccount.is_active == True,
                IntegrationAccount.status == "connected",
            )
            .first()
        )

    def _load_or_create_state(self, account):
        from app.models.discord_bot_sync_state import DiscordBotSyncState

        state = (
            self.db.query(DiscordBotSyncState)
            .filter(DiscordBotSyncState.integration_account_id == account.id)
            .first()
        )
        if not state:
            state = DiscordBotSyncState(
                integration_account_id=account.id,
                user_id=account.user_id,
                is_active=True,
                channel_offsets={},
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
        """Agents wired to THIS discord bot account for customer chat.

        Primary: explicit AgentIntegration mapping with integration_account_id
        set to this account. Fallback: a generic discord link created WITHOUT
        an account binding — resolved against the account's owner so the bot
        still reaches the owner's active discord agents. Strict per-account
        mappings are never widened this way (multi-tenant safe).
        """
        from app.models.agent import AIAgent, LifecycleStatus
        from app.models.agent_integration import AgentIntegration
        from app.models.integration import Integration

        integration = (
            self.db.query(Integration).filter(Integration.name == "discord").first()
        )
        if not integration:
            return []

        def _agents_for(links):
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

        explicit = (
            self.db.query(AgentIntegration)
            .filter(
                AgentIntegration.integration_id == integration.id,
                AgentIntegration.integration_account_id == account.id,
                AgentIntegration.is_active == True,
            )
            .all()
        )
        agents = _agents_for(explicit)
        if agents:
            return agents

        generic = (
            self.db.query(AgentIntegration)
            .join(AIAgent, AIAgent.id == AgentIntegration.agent_id)
            .filter(
                AgentIntegration.integration_id == integration.id,
                AgentIntegration.integration_account_id.is_(None),
                AgentIntegration.is_active == True,
                AIAgent.user_id == account.user_id,
                AIAgent.lifecycle_status == LifecycleStatus.ACTIVE,
            )
            .all()
        )
        return _agents_for(generic)

    def _fire_for_message(self, account, msg: Dict[str, Any]) -> int:
        from app.services.trigger_service import TriggerService

        trigger_service = TriggerService(self.db)
        event_id = f"{msg['channel_id']}:{msg['message_id']}"
        fired = 0

        for agent in self._linked_agents(account):
            try:
                trigger = trigger_service.fire_integration_trigger(
                    agent_id=agent.id,
                    integration_name="discord",
                    event_type="discord_message_received",
                    event_id=event_id,
                    payload={
                        "message_id": msg["message_id"],
                        "channel_id": msg["channel_id"],
                        "channel_name": msg.get("channel_name", ""),
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
                        "Discord message trigger created",
                        extra={
                            "agent_id": str(agent.id),
                            "trigger_id": str(trigger.id),
                            "channel_id": msg["channel_id"],
                            "message_id": msg["message_id"],
                        },
                    )
            except Exception:
                logger.error(
                    "Failed to fire Discord trigger for agent",
                    extra={"agent_id": str(agent.id), "message_id": msg.get("message_id")},
                    exc_info=True,
                )
        return fired

    # ------------------------------------------------------------------
    # Discord REST helpers
    # ------------------------------------------------------------------

    async def _fetch_dm_channels(self, client: httpx.AsyncClient, bot_token: str) -> List[Dict[str, Any]]:
        """DM channels the bot participates in."""
        resp = await client.get(f"{DC_API}/users/@me/channels", headers=_headers(bot_token))
        resp.raise_for_status()
        return resp.json() or []

    async def _fetch_watch_channels(self, client: httpx.AsyncClient, bot_token: str) -> tuple:
        """Channels worth polling + the bot's own user id.

        Returns ``(bot_user_id, channels)`` where channels covers:
        - DM channels (type 1) the bot shares with customers
        - Text channels (type 0) of every guild the bot is in — the bot only
          answers mentions in those (enforced by the caller)
        """
        resp = await client.get(f"{DC_API}/users/@me", headers=_headers(bot_token))
        resp.raise_for_status()
        bot_user_id = str((resp.json() or {}).get("id", ""))

        dm_channels = await self._fetch_dm_channels(client, bot_token)

        guild_channels: List[Dict[str, Any]] = []
        try:
            guilds_resp = await client.get(f"{DC_API}/users/@me/guilds", headers=_headers(bot_token))
            guilds_resp.raise_for_status()
            for guild in guilds_resp.json() or []:
                guild_id = guild.get("id")
                if not guild_id:
                    continue
                try:
                    gch_resp = await client.get(
                        f"{DC_API}/guilds/{guild_id}/channels",
                        headers=_headers(bot_token),
                    )
                    gch_resp.raise_for_status()
                    guild_channels.extend(
                        ch for ch in (gch_resp.json() or [])
                        if ch.get("type") == 0  # text channels only
                    )
                except httpx.HTTPStatusError:
                    continue  # no access to this guild's channel list
        except httpx.HTTPStatusError:
            pass  # guilds listing failed — DMs still work

        channels = list(dm_channels) + guild_channels
        return bot_user_id, channels

    async def _fetch_messages_after(
        self,
        client: httpx.AsyncClient,
        bot_token: str,
        channel_id: str,
        after_message_id: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Messages in a channel newer than ``after_message_id``, oldest first."""
        params: Dict[str, Any] = {"limit": limit}
        if after_message_id:
            params["after"] = str(after_message_id)
        resp = await client.get(
            f"{DC_API}/channels/{channel_id}/messages",
            headers=_headers(bot_token),
            params=params,
        )
        resp.raise_for_status()
        # Discord returns newest-first; invert to oldest-first for processing.
        return list(reversed(resp.json() or []))

    # ------------------------------------------------------------------
    # Account poll
    # ------------------------------------------------------------------

    async def check_account(self, integration_account_id) -> Dict[str, Any]:
        """One REST polling cycle for one discord bot account."""
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

        cap = int(getattr(settings, "DISCORD_BOT_MAX_TRIGGERS_PER_CYCLE", 10))
        fetch_limit = int(getattr(settings, "DISCORD_BOT_FETCH_LIMIT", 20))

        offsets: Dict[str, str] = dict(state.channel_offsets or {})
        baselining = not bool(offsets)

        fired = 0
        events: List[Dict[str, Any]] = []

        async with httpx.AsyncClient() as client:
            try:
                bot_user_id, channels = await self._fetch_watch_channels(client, bot_token)
            except httpx.HTTPStatusError as exc:
                error = _scrub_token(
                    f"Discord API error {exc.response.status_code}", credentials
                )
                state.sync_error = error[:500]
                state.consecutive_errors = (state.consecutive_errors or 0) + 1
                self.db.commit()
                return {"skipped": error}

            mention_prefixes = (
                f"<@{bot_user_id}>",
                f"<@!{bot_user_id}>",
            ) if bot_user_id else ()

            for ch in channels:
                channel_id = str(ch.get("id", ""))
                if not channel_id:
                    continue

                # Guild (server) channels: the bot only answers when mentioned —
                # it must not react to every message in a busy server channel.
                # DM channels (type 1): every customer message is answered.
                is_dm = ch.get("type") == 1
                if baselining:
                    watermark = offsets.get(channel_id, "")
                else:
                    watermark = offsets.get(channel_id, "")

                try:
                    messages = await self._fetch_messages_after(
                        client, bot_token, channel_id, watermark, fetch_limit
                    )
                except httpx.HTTPStatusError:
                    # 403 (missing access) / 404 (deleted channel) — skip this
                    # channel but keep polling the rest.
                    continue

                for message in messages:
                    message_id = str(message.get("id", ""))
                    if not message_id or message_id <= watermark:
                        continue

                    author = message.get("author") or {}
                    text = str(message.get("content", "") or "").strip()

                    # Track the newest id per channel regardless of outcome —
                    # skipped messages never re-fire (matches Telegram acking).
                    offsets[channel_id] = message_id

                    # Baseline pass: first poll acknowledges backlog silently.
                    if baselining:
                        continue

                    # No bot senders, no empty messages → no bot-to-bot loops.
                    if author.get("is_bot") or author.get("bot") or not text:
                        continue

                    # Guild channels: only answer when the bot is mentioned.
                    if not is_dm:
                        mentioned = any(m in text for m in mention_prefixes)
                        if not mentioned:
                            continue
                        # Strip the mention from the text passed to the LLM.
                        for m in mention_prefixes:
                            text = text.replace(m, "").strip()

                    if fired >= cap:
                        continue  # keep advancing watermark; rest waits

                    msg = {
                        "message_id": message_id,
                        "channel_id": channel_id,
                        "channel_name": ch.get("name") or (author.get("username") or "DM"),
                        "sender_id": str(author.get("id", "")),
                        "from_address": f"@{author.get('username')}" if author.get("username") else "unknown",
                        "text": text[:2000],
                        "date": message.get("timestamp", "") or datetime.now(timezone.utc).isoformat(),
                    }
                    # Real-time feedback: show "typing…" the moment a customer
                    # message is picked up; the reply path sustains it.
                    send_typing_action(bot_token, channel_id)

                    fired += self._fire_for_message(account, msg)
                    events.append({
                        "message_id": msg["message_id"],
                        "channel_id": msg["channel_id"],
                        "channel_name": msg["channel_name"],
                        "sender_id": msg["sender_id"],
                        "text": text[:200],
                        "account_id": str(account.id),
                    })

        state.channel_offsets = offsets
        state.total_processed = (state.total_processed or 0) + fired
        state.last_sync_at = datetime.now(timezone.utc).isoformat()
        state.consecutive_errors = 0
        state.sync_error = None
        self.db.commit()

        result: Dict[str, Any] = {"new_messages": fired, "events": events}
        if baselining:
            result["baselined_channels"] = len(offsets)
        return result

    def record_failure(self, integration_account_id, error: str) -> None:
        """Persist a scrubbed sync error for one discord bot account. Best-effort."""
        from app.models.discord_bot_sync_state import DiscordBotSyncState

        state = (
            self.db.query(DiscordBotSyncState)
            .filter(DiscordBotSyncState.integration_account_id == integration_account_id)
            .first()
        )
        if not state:
            return
        state.consecutive_errors = (state.consecutive_errors or 0) + 1
        state.sync_error = error[:500]
        self.db.commit()


# ----------------------------------------------------------------------
# Scheduler single-pass (mirrors check_all_telegram_bots)
# ----------------------------------------------------------------------

def _check_all_sync() -> List[Dict[str, Any]]:
    """Sync pass: self-heal discord bot states, poll due accounts, collect events."""
    from app.database.session import SessionLocal
    from app.database.retry import db_retry
    from app.models.integration import Integration
    from app.models.integration_account import IntegrationAccount
    from app.models.discord_bot_sync_state import DiscordBotSyncState

    @db_retry(max_retries=2, base_delay=1.0)
    def _due_accounts(db) -> list:
        now = datetime.now(timezone.utc)
        integration = (
            db.query(Integration).filter(Integration.name == "discord").first()
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
            for s in db.query(DiscordBotSyncState).all()
        }
        created = False
        for account in accounts:
            if account.id in have:
                continue
            db.add(DiscordBotSyncState(
                integration_account_id=account.id,
                user_id=account.user_id,
                is_active=True,
                channel_offsets={},
                total_processed=0,
                consecutive_errors=0,
            ))
            created = True
            logger.warning(
                "Created missing DiscordBotSyncState for connected Discord bot",
                extra={"integration_account_id": str(account.id)},
            )
        if created:
            db.commit()

        due = []
        for account in accounts:
            state = (
                db.query(DiscordBotSyncState)
                .filter(DiscordBotSyncState.integration_account_id == account.id)
                .first()
            )
            if not state or not state.is_active:
                continue
            if state.last_sync_at:
                try:
                    last = datetime.fromisoformat(state.last_sync_at)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    gap = int(getattr(settings, "DISCORD_BOT_CHANNEL_GAP_SECONDS", 2))
                    if (now - last).total_seconds() < gap:
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
            service = DiscordBotMonitorService(db)
            result = asyncio.run(service.check_account(account_id))
            if result.get("new_messages"):
                logger.info(
                    f"Discord Bot: {result['new_messages']} new customer messages triggered",
                    extra={"integration_account_id": str(account_id)},
                )
            collected.extend(result.get("events") or [])
        except Exception as e:
            logger.error(
                f"Discord bot check failed for account {account_id}: {e}",
                exc_info=True,
            )
            try:
                from app.utils.encryption import decrypt_field
                from app.models.integration_account import IntegrationAccount as _IA

                account = db.query(_IA).filter(_IA.id == UUID(account_id)).first()
                creds = {
                    k: decrypt_field(str(v)) for k, v in (account.credentials or {}).items()
                } if account else {}
                DiscordBotMonitorService(db).record_failure(
                    account_id, _scrub_token(str(e), creds)
                )
            except Exception:
                logger.debug("Failure bookkeeping skipped", exc_info=True)
        finally:
            db.close()

    return collected


async def check_all_discord_bots():
    """Single Discord Bot check pass — called by the scheduler."""
    from app.events.publisher import publish_discord_message_received

    try:
        collected = await asyncio.to_thread(_check_all_sync)
    except Exception as e:
        logger.error(f"Discord bot monitoring error: {e}", exc_info=True)
        return

    for ev in collected:
        try:
            await publish_discord_message_received(
                message_id=ev.get("message_id", ""),
                channel_id=ev.get("channel_id", ""),
                channel_name=ev.get("channel_name", ""),
                sender_id=ev.get("sender_id", ""),
                text=ev.get("text", ""),
                account_id=ev.get("account_id") or None,
            )
        except Exception as e:
            logger.warning(f"Failed to publish Discord message event: {e}")
