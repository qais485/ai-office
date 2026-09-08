"""Telegram integration provider (Bot Token auth)."""
import logging
from typing import Any, Dict, Optional

import httpx

from app.services.integration_providers.base import IntegrationProvider, ProviderResult

logger = logging.getLogger(__name__)

TG_API = "https://api.telegram.org"


class TelegramProvider(IntegrationProvider):
    @property
    def integration_name(self) -> str:
        return "telegram"

    async def execute_action(self, action: str, parameters: Dict[str, Any], access_token: Optional[str] = None, credentials: Optional[Dict[str, Any]] = None) -> ProviderResult:
        # Fall back to "api_key" for accounts connected before the Bot/Account
        # split, when the frontend stored the bot token under that key.
        bot_token = (credentials or {}).get("bot_token") or (credentials or {}).get("api_key") or access_token
        if not bot_token:
            return ProviderResult(success=False, error="No bot token provided")
        handlers = {
            "send_message": self._send_message,
            "read_messages": self._read_messages,
        }
        handler = handlers.get(action)
        if not handler:
            return ProviderResult(success=False, error=f"Unknown action: {action}")
        try:
            return await handler(parameters, bot_token)
        except httpx.HTTPStatusError as exc:
            return ProviderResult(success=False, error=f"Telegram API error {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Telegram provider error")
            return ProviderResult(success=False, error=str(exc))

    async def _send_message(self, params: dict, token: str) -> ProviderResult:
        chat_id = params.get("chat_id")
        text = params.get("text", "")
        if not chat_id:
            return ProviderResult(success=False, error="'chat_id' is required")
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{TG_API}/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            return ProviderResult(success=False, error=str(data.get("description", "Unknown error")))
        result = data.get("result", {})
        return ProviderResult(success=True, data={"message_id": result.get("message_id"), "chat_id": result.get("chat", {}).get("id")})

    async def _read_messages(self, params: dict, token: str) -> ProviderResult:
        offset = params.get("offset", 0)
        limit = params.get("limit", 10)
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{TG_API}/bot{token}/getUpdates", params={"offset": offset, "limit": limit, "timeout": 5}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            return ProviderResult(success=False, error=str(data.get("description")))
        messages = []
        for u in data.get("result", []):
            msg = u.get("message", {})
            messages.append({"update_id": u.get("update_id"), "message_id": msg.get("message_id"), "text": msg.get("text", ""), "from": msg.get("from", {}).get("username", "")})
        return ProviderResult(success=True, data={"messages": messages})

    async def test_connection(self, access_token=None, credentials=None) -> ProviderResult:
        bot_token = (credentials or {}).get("bot_token") or (credentials or {}).get("api_key") or access_token
        if not bot_token:
            return ProviderResult(success=False, error="No bot token")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{TG_API}/bot{bot_token}/getMe", timeout=10)
                resp.raise_for_status()
                data = resp.json()
            if not data.get("ok"):
                return ProviderResult(success=False, error=data.get("description"))
            bot = data.get("result", {})
            return ProviderResult(success=True, data={"bot_username": bot.get("username"), "bot_name": bot.get("first_name")})
        except Exception as exc:
            return ProviderResult(success=False, error=str(exc))

    async def revoke(self, access_token=None, refresh_token=None, credentials=None) -> ProviderResult:
        return ProviderResult(success=True, metadata={"note": "Telegram bot tokens are invalidated via BotFather"})
