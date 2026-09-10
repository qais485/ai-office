"""Discord integration provider (Bot Token auth, Bot REST API v10)."""
import logging
from typing import Any, Dict, Optional

import httpx

from app.services.integration_providers.base import IntegrationProvider, ProviderResult

logger = logging.getLogger(__name__)

DC_API = "https://discord.com/api/v10"


class DiscordProvider(IntegrationProvider):
    @property
    def integration_name(self) -> str:
        return "discord"

    async def execute_action(self, action: str, parameters: Dict[str, Any], access_token: Optional[str] = None, credentials: Optional[Dict[str, Any]] = None) -> ProviderResult:
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
            return ProviderResult(success=False, error=f"Discord API error {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Discord provider error")
            return ProviderResult(success=False, error=str(exc))

    async def _send_message(self, params: dict, token: str) -> ProviderResult:
        channel_id = params.get("channel_id") or params.get("chat_id")
        text = params.get("text", "")
        if not channel_id:
            return ProviderResult(success=False, error="'channel_id' is required")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{DC_API}/channels/{channel_id}/messages",
                headers=self._headers(token),
                json={"content": text},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"message_id": data.get("id"), "channel_id": (data.get("channel_id") or str(channel_id))})

    async def _read_messages(self, params: dict, token: str) -> ProviderResult:
        channel_id = params.get("channel_id") or params.get("chat_id")
        if not channel_id:
            return ProviderResult(success=False, error="'channel_id' is required")
        limit = min(int(params.get("limit", 10) or 10), 100)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{DC_API}/channels/{channel_id}/messages",
                headers=self._headers(token),
                params={"limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        messages = [
            {
                "message_id": m.get("id"),
                "text": m.get("content", ""),
                "from": (m.get("author") or {}).get("username", ""),
                "bot": bool((m.get("author") or {}).get("bot", False)),
            }
            for m in data
        ]
        return ProviderResult(success=True, data={"messages": messages})

    @staticmethod
    def _headers(token: str) -> Dict[str, str]:
        return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}

    async def test_connection(self, access_token=None, credentials=None) -> ProviderResult:
        bot_token = (credentials or {}).get("bot_token") or (credentials or {}).get("api_key") or access_token
        if not bot_token:
            return ProviderResult(success=False, error="No bot token")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{DC_API}/users/@me", headers=self._headers(bot_token), timeout=10)
                resp.raise_for_status()
                data = resp.json()
            return ProviderResult(success=True, data={"bot_username": data.get("username"), "bot_id": data.get("id")})
        except Exception as exc:
            return ProviderResult(success=False, error=str(exc))

    async def revoke(self, access_token=None, refresh_token=None, credentials=None) -> ProviderResult:
        return ProviderResult(success=True, metadata={"note": "Discord bot tokens are invalidated in the Developer Portal"})
