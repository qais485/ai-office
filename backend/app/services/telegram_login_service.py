"""Interactive Telegram Account login flow (Telethon / MTProto).

Multi-step flow so users never paste a session string by hand:

    1. start_login       api_id + api_hash + phone  -> Telegram sends a code
    2. verify_code       the code Telegram sent     -> connected (or 2FA step)
    3. verify_password   2FA password, if enabled   -> connected
    +  cancel_login      aborts a pending login

Between steps only loop-agnostic data is persisted in memory: the StringSession
payload that carries the MTProto auth key created by ``send_code_request``.
A fresh ``TelegramClient`` is created per step and re-connected from that
payload, which keeps the flow safe across the short-lived event loops created
by ``run_async()``. On success the final session string is stored through
``IntegrationService.connect_account`` so every credential value is encrypted
at rest (the provider reads it back from ``credentials["session"]``).
"""
import logging
import re
import threading
import time
from typing import Any, Dict, Optional

from app.services.integration_service import IntegrationService
from app.services.integration_providers.telegram_account import _validate_credentials

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"^\+\d{6,15}$")
_CODE_RE = re.compile(r"^\d{4,8}$")
_PENDING_TTL_SECONDS = 600  # Telegram login codes expire well before this

_pending_lock = threading.Lock()
_pending: Dict[str, Dict[str, Any]] = {}


class TelegramLoginError(ValueError):
    """User-facing login failure (invalid input, bad code, flood wait, ...)."""


def _pending_key(user_id, integration_id) -> str:
    return f"{user_id}:{integration_id}"


def _purge_expired_locked() -> None:
    now = time.time()
    for key in [k for k, v in _pending.items() if now - v["created_at"] > _PENDING_TTL_SECONDS]:
        _pending.pop(key, None)


def _normalize_phone(raw: str) -> str:
    normalized = re.sub(r"[\s()\-.]", "", str(raw or "")).strip()
    if normalized and not normalized.startswith("+"):
        normalized = f"+{normalized}"
    return normalized


class TelegramLoginService:
    INTEGRATION_NAME = "telegram_account"

    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # helpers                                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _load_telethon():
        try:
            from telethon import TelegramClient  # type: ignore
            from telethon.sessions import StringSession  # type: ignore
            return TelegramClient, StringSession
        except ImportError:
            raise TelegramLoginError(
                "telethon is not installed on the server — add it with: pip install telethon"
            )

    def _get_integration(self, integration_id):
        integration = IntegrationService(self.db).get_integration(integration_id)
        if not integration:
            raise TelegramLoginError("Integration not found")
        if integration.name != self.INTEGRATION_NAME:
            raise TelegramLoginError("This login flow is only available for the Telegram Account integration")
        return integration

    def _get_state(self, user_id, integration_id) -> Dict[str, Any]:
        key = _pending_key(user_id, integration_id)
        with _pending_lock:
            _purge_expired_locked()
            state = _pending.get(key)
        if not state:
            raise TelegramLoginError(
                "No login in progress — start again with your API ID, API Hash and phone number"
            )
        return state

    def _clear_state(self, user_id, integration_id) -> None:
        with _pending_lock:
            _pending.pop(_pending_key(user_id, integration_id), None)

    @staticmethod
    def _is_password_needed(exc: Exception) -> bool:
        try:
            from telethon.errors import SessionPasswordNeededError  # type: ignore
            return isinstance(exc, SessionPasswordNeededError)
        except ImportError:
            return False

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        name = type(exc).__name__
        if name == "FloodWaitError":
            wait = getattr(exc, "seconds", None)
            return (
                f"Telegram rate limit reached — try again in {wait} seconds"
                if wait else "Telegram rate limit reached — try again later"
            )
        messages = {
            "PhoneNumberInvalidError": "The phone number is invalid. Use international format, e.g. +989123456789",
            "PhoneCodeInvalidError": "The code you entered is incorrect",
            "PhoneCodeExpiredError": "The code has expired — start the login again to receive a new one",
            "PhoneNumberUnoccupiedError": "No Telegram account exists for this phone number",
            "PasswordHashInvalidError": "Incorrect two-step verification password",
            "ApiIdInvalidError": "Invalid API ID / API Hash pair — check your values at my.telegram.org",
            "ApiIdPublishedFloodError": "This API ID / API Hash pair is blocked by Telegram (app published or flooded)",
        }
        return messages.get(name) or f"Telegram login failed: {exc}"

    def _finalize(self, user_id, integration_id, state: Dict[str, Any], session_string: str, me: Any) -> dict:
        """Persist the final session through the normal (encrypting) path."""
        display_name = (
            getattr(me, "username", None)
            or getattr(me, "first_name", None)
            or "Telegram Account"
        )[:100]
        account = IntegrationService(self.db).connect_account(
            user_id=user_id,
            integration_id=integration_id,
            credentials={
                "api_id": state["api_id"],
                "api_hash": state["api_hash"],
                "session": session_string,
            },
            display_name=display_name,
        )
        logger.info("Telegram Account login completed for user %s", user_id)
        return {
            "status": "connected",
            "username": getattr(me, "username", None),
            "name": getattr(me, "first_name", None) or "",
            "account_id": str(account.id),
        }

    # ------------------------------------------------------------------ #
    # steps                                                               #
    # ------------------------------------------------------------------ #
    def start_login(self, user_id, integration_id, api_id: str, api_hash: str, phone: str) -> dict:
        self._get_integration(integration_id)

        error = _validate_credentials({"api_id": api_id, "api_hash": api_hash})
        if error:
            raise TelegramLoginError(error)

        normalized = _normalize_phone(phone)
        if not _PHONE_RE.match(normalized):
            raise TelegramLoginError(
                "Enter a valid phone number in international format, e.g. +989123456789"
            )

        TelegramClient, StringSession = self._load_telethon()

        async def _request_code():
            client = TelegramClient(StringSession(), int(str(api_id).strip()), str(api_hash).strip())
            await client.connect()
            try:
                sent = await client.send_code_request(normalized)
                # phone_code_hash binds the sent code to this authorization
                # attempt; sign_in from a fresh client fails without it.
                return (
                    client.session.save(),
                    getattr(sent, "phone_code_hash", None),
                    getattr(sent, "code_length", None),
                )
            finally:
                await client.disconnect()

        from app.utils.async_utils import run_async
        try:
            temp_session, phone_code_hash, code_length = run_async(_request_code())
        except TelegramLoginError:
            raise
        except Exception as exc:
            raise TelegramLoginError(self._friendly_error(exc)) from exc

        key = _pending_key(user_id, integration_id)
        with _pending_lock:
            _purge_expired_locked()
            _pending[key] = {
                "api_id": str(api_id).strip(),
                "api_hash": str(api_hash).strip(),
                "phone": normalized,
                "temp_session": temp_session,
                "phone_code_hash": phone_code_hash,
                "password_required": False,
                "created_at": time.time(),
            }
        return {"status": "code_sent", "phone": normalized, "code_length": code_length}

    def verify_code(self, user_id, integration_id, code: str) -> dict:
        code = str(code or "").strip()
        if not _CODE_RE.match(code):
            raise TelegramLoginError("Enter the numeric code Telegram sent you")

        state = self._get_state(user_id, integration_id)
        if not state.get("phone_code_hash"):
            raise TelegramLoginError(
                "Login state is missing its code hash — start the login again"
            )
        TelegramClient, StringSession = self._load_telethon()

        async def _sign_in():
            client = TelegramClient(
                StringSession(state["temp_session"]),
                int(state["api_id"]),
                state["api_hash"],
            )
            await client.connect()
            try:
                if not await client.is_user_authorized():
                    await client.sign_in(
                        phone=state["phone"],
                        code=code,
                        phone_code_hash=state["phone_code_hash"],
                    )
                session_string = client.session.save()
                me = await client.get_me()
                return session_string, me
            except Exception:
                # Persist the (unchanged) temp session so the code can be retried
                try:
                    state["temp_session"] = client.session.save()
                except Exception:
                    pass
                raise
            finally:
                await client.disconnect()

        from app.utils.async_utils import run_async
        try:
            session_string, me = run_async(_sign_in())
        except Exception as exc:
            if self._is_password_needed(exc):
                with _pending_lock:
                    pending = _pending.get(_pending_key(user_id, integration_id))
                    if pending:
                        pending["password_required"] = True
                return {"status": "2fa_required"}
            raise TelegramLoginError(self._friendly_error(exc)) from exc

        self._clear_state(user_id, integration_id)
        return self._finalize(user_id, integration_id, state, session_string, me)

    def verify_password(self, user_id, integration_id, password: str) -> dict:
        state = self._get_state(user_id, integration_id)
        if not state.get("password_required"):
            raise TelegramLoginError("This login attempt does not require a password step")
        password = str(password or "")
        if not password:
            raise TelegramLoginError("Enter your two-step verification password")

        TelegramClient, StringSession = self._load_telethon()

        async def _sign_in_password():
            client = TelegramClient(
                StringSession(state["temp_session"]),
                int(state["api_id"]),
                state["api_hash"],
            )
            await client.connect()
            try:
                await client.sign_in(password=password)
                session_string = client.session.save()
                me = await client.get_me()
                return session_string, me
            finally:
                await client.disconnect()

        from app.utils.async_utils import run_async
        try:
            session_string, me = run_async(_sign_in_password())
        except Exception as exc:
            raise TelegramLoginError(self._friendly_error(exc)) from exc

        self._clear_state(user_id, integration_id)
        return self._finalize(user_id, integration_id, state, session_string, me)

    def cancel_login(self, user_id, integration_id) -> dict:
        self._get_integration(integration_id)
        self._clear_state(user_id, integration_id)
        return {"status": "cancelled"}
