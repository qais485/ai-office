"""Telegram user-account integration provider (MTProto via API ID + API Hash).

Independent from the Telegram *Bot* integration (which uses a BotFather bot
token): this provider authenticates as a real user account with the api_id /
api_hash pair issued at my.telegram.org.

Stored credentials shape (IntegrationAccount.credentials, encrypted per key):
    {
        "api_id":   "1234567",                                  # required
        "api_hash": "0123456789abcdef0123456789abcdef",         # required
        "session":  "<Telethon StringSession payload>"          # optional at
                                                                # connect time;
                                                                # required for
                                                                # real actions
    }

The optional ``session`` string is produced by a one-time interactive Telethon
login (phone + code) using the same api_id / api_hash pair. Until it is bound,
credentials are validated and stored, but message actions report a clear error
instead of silently failing. Telethon is imported lazily so the provider
registry never breaks when the library is not installed.
"""
import logging
import re
from typing import Any, Dict, Optional

from app.services.integration_providers.base import IntegrationProvider, ProviderResult

logger = logging.getLogger(__name__)

# api_id is a positive integer assigned per application at my.telegram.org
_API_ID_RE = re.compile(r"^\d{1,10}$")
# api_hash is the 32-character hex digest paired with that api_id
_API_HASH_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def _validate_credentials(credentials: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return an error message for missing/malformed credentials, else None."""
    creds = credentials or {}
    api_id = str(creds.get("api_id") or "").strip()
    api_hash = str(creds.get("api_hash") or "").strip()
    if not api_id and not api_hash:
        return "No API ID / API Hash provided"
    if not api_id:
        return "API ID is required (get it at my.telegram.org)"
    if not api_hash:
        return "API Hash is required (get it at my.telegram.org)"
    if not _API_ID_RE.match(api_id):
        return "API ID must be a numeric ID (a whole number, e.g. 1234567)"
    if not _API_HASH_RE.match(api_hash):
        return "API Hash must be the 32-character hex value from my.telegram.org"
    return None


def _load_telethon():
    """Lazily import Telethon; returns (TelegramClient, StringSession) or (None, None)."""
    try:
        from telethon import TelegramClient  # type: ignore
        from telethon.sessions import StringSession  # type: ignore
        return TelegramClient, StringSession
    except ImportError:
        return None, None


class TelegramAccountProvider(IntegrationProvider):
    @property
    def integration_name(self) -> str:
        return "telegram_account"

    @staticmethod
    def _session_string(credentials: Optional[Dict[str, Any]]) -> str:
        return str((credentials or {}).get("session") or "").strip()

    @staticmethod
    def _clean_params(credentials: Optional[Dict[str, Any]]) -> Dict[str, str]:
        creds = credentials or {}
        return {
            "api_id": str(creds.get("api_id") or "").strip(),
            "api_hash": str(creds.get("api_hash") or "").strip(),
        }

    @staticmethod
    def _scrub_secrets(text: str, credentials: Optional[Dict[str, Any]]) -> str:
        """Keep the API Hash and session string out of agent-visible errors.

        Agent tool results surface provider error strings verbatim; credential
        values must never appear in them, even inside library exception text.
        """
        safe = str(text or "")
        creds = credentials or {}
        for key in ("api_hash", "session"):
            secret = str(creds.get(key) or "").strip()
            if secret:
                safe = safe.replace(secret, "***")
        return safe

    async def execute_action(
        self,
        action: str,
        parameters: Dict[str, Any],
        access_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        error = _validate_credentials(credentials)
        if error:
            return ProviderResult(success=False, error=error)

        handlers = {
            "send_message": self._send_message,
            "read_history": self._read_history,
        }
        handler = handlers.get(action)
        if not handler:
            return ProviderResult(success=False, error=f"Unknown action: {action}")

        creds = self._clean_params(credentials)
        session_string = self._session_string(credentials)
        if not session_string:
            return ProviderResult(
                success=False,
                error=(
                    "This Telegram Account has no bound MTProto session yet. "
                    "Reconnect with a Telethon session string (phone login) to "
                    "run account actions."
                ),
            )

        TelegramClient, StringSession = _load_telethon()
        if not TelegramClient:
            return ProviderResult(
                success=False,
                error="telethon is not installed on the server (required for Telegram Account actions)",
            )

        try:
            client = TelegramClient(StringSession(session_string), int(creds["api_id"]), creds["api_hash"])
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return ProviderResult(
                    success=False,
                    error="The stored session is not authorized anymore — generate a new session string",
                )
            try:
                return await handler(parameters, client)
            finally:
                await client.disconnect()
        except Exception as exc:
            logger.exception("Telegram Account provider error")
            return ProviderResult(success=False, error=self._scrub_secrets(str(exc), credentials))

    async def _send_message(self, params: dict, client: Any) -> ProviderResult:
        chat_id = params.get("chat_id")
        text = params.get("text", "")
        if not chat_id:
            return ProviderResult(success=False, error="'chat_id' is required")
        entity = await client.get_entity(chat_id)
        message = await client.send_message(entity, text)
        return ProviderResult(
            success=True,
            data={"message_id": message.id, "chat_id": message.chat_id},
        )

    async def _read_history(self, params: dict, client: Any) -> ProviderResult:
        chat_id = params.get("chat_id")
        if not chat_id:
            return ProviderResult(success=False, error="'chat_id' is required")
        limit = int(params.get("limit", 10))
        entity = await client.get_entity(chat_id)
        messages = await client.get_messages(entity, limit=limit)
        return ProviderResult(
            success=True,
            data={
                "messages": [
                    {
                        "id": m.id,
                        "text": m.message or "",
                        "sender_id": m.sender_id,
                        "date": m.date.isoformat() if m.date else None,
                    }
                    for m in messages
                ]
            },
        )

    async def test_connection(
        self,
        access_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        error = _validate_credentials(credentials)
        if error:
            return ProviderResult(success=False, error=error)

        creds = self._clean_params(credentials)
        session_string = self._session_string(credentials)

        if not session_string:
            # No MTProto session bound yet: the credential pair can only be
            # format-validated at this stage (MTProto has no keyless probe).
            return ProviderResult(
                success=True,
                data={
                    "api_id": creds["api_id"],
                    "verified": "format",
                    "note": (
                        "API ID / API Hash are valid in format. Reconnect with a "
                        "Telethon session string to fully verify and enable actions."
                    ),
                },
            )

        TelegramClient, StringSession = _load_telethon()
        if not TelegramClient:
            return ProviderResult(
                success=False,
                error="telethon is not installed on the server (required to test a bound Telegram session)",
            )

        try:
            client = TelegramClient(StringSession(session_string), int(creds["api_id"]), creds["api_hash"])
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return ProviderResult(
                    success=False,
                    error="The stored session is not authorized anymore — generate a new session string",
                )
            me = await client.get_me()
            await client.disconnect()
            return ProviderResult(
                success=True,
                data={
                    "username": me.username,
                    "name": getattr(me, "first_name", None) or "",
                    "verified": "session",
                },
            )
        except Exception as exc:
            logger.exception("Telegram Account connection test failed")
            return ProviderResult(success=False, error=str(exc))

    async def revoke(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        return ProviderResult(
            success=True,
            metadata={
                "note": (
                    "Revoke access by terminating the session from Telegram "
                    "Settings → Devices, or manage the app at my.telegram.org."
                )
            },
        )
