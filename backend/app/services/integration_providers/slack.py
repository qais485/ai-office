"""Slack integration provider."""
import logging
from typing import Any, Dict, Optional

import httpx

from app.services.integration_providers.base import IntegrationProvider, ProviderResult

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"


class SlackProvider(IntegrationProvider):
    @property
    def integration_name(self) -> str:
        return "slack"

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

    async def execute_action(self, action: str, parameters: Dict[str, Any], access_token: Optional[str] = None, credentials: Optional[Dict[str, Any]] = None) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token")
        handlers = {
            "send_message": self._send_message,
            "read_messages": self._read_messages,
            "manage_channels": self._manage_channels,
        }
        handler = handlers.get(action)
        if not handler:
            return ProviderResult(success=False, error=f"Unknown action: {action}")
        try:
            return await handler(parameters, access_token)
        except httpx.HTTPStatusError as exc:
            return ProviderResult(success=False, error=f"Slack API error {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Slack provider error")
            return ProviderResult(success=False, error=str(exc))

    async def _send_message(self, params: dict, token: str) -> ProviderResult:
        channel = params.get("channel")
        text = params.get("text", "")
        if not channel:
            return ProviderResult(success=False, error="'channel' is required")
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{SLACK_API}/chat.postMessage", headers=self._headers(token), json={"channel": channel, "text": text}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            return ProviderResult(success=False, error=data.get("error", "Unknown Slack error"))
        return ProviderResult(success=True, data={"ts": data.get("ts"), "channel": data.get("channel")})

    async def _read_messages(self, params: dict, token: str) -> ProviderResult:
        channel = params.get("channel")
        limit = params.get("limit", 20)
        if not channel:
            return ProviderResult(success=False, error="'channel' is required")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SLACK_API}/conversations.history", headers=self._headers(token), params={"channel": channel, "limit": limit}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            return ProviderResult(success=False, error=data.get("error"))
        messages = [{"text": m.get("text"), "user": m.get("user"), "ts": m.get("ts")} for m in data.get("messages", [])]
        return ProviderResult(success=True, data={"messages": messages, "has_more": data.get("has_more", False)})

    async def _manage_channels(self, params: dict, token: str) -> ProviderResult:
        action_type = params.get("action_type", "list")
        async with httpx.AsyncClient() as client:
            if action_type == "list":
                resp = await client.get(f"{SLACK_API}/conversations.list", headers=self._headers(token), params={"types": "public_channel,private_channel", "limit": 100}, timeout=15)
            elif action_type == "info":
                channel = params.get("channel")
                resp = await client.get(f"{SLACK_API}/conversations.info", headers=self._headers(token), params={"channel": channel}, timeout=15)
            else:
                return ProviderResult(success=False, error=f"Unknown manage_channels action: {action_type}")
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            return ProviderResult(success=False, error=data.get("error"))
        return ProviderResult(success=True, data=data)

    async def test_connection(self, access_token=None, credentials=None) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{SLACK_API}/auth.test", headers=self._headers(access_token), timeout=10)
                resp.raise_for_status()
                data = resp.json()
            if not data.get("ok"):
                return ProviderResult(success=False, error=data.get("error"))
            return ProviderResult(success=True, data={"team": data.get("team"), "user": data.get("user")})
        except Exception as exc:
            return ProviderResult(success=False, error=str(exc))

    async def revoke(self, access_token=None, refresh_token=None, credentials=None) -> ProviderResult:
        return ProviderResult(success=True, metadata={"note": "Slack tokens are invalidated by app uninstall"})
