"""Instagram (Meta Graph API) integration provider."""
import logging
from typing import Any, Dict, Optional

import httpx

from app.services.integration_providers.base import IntegrationProvider, ProviderResult

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v21.0"


class InstagramProvider(IntegrationProvider):
    @property
    def integration_name(self) -> str:
        return "instagram"

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    async def execute_action(self, action: str, parameters: Dict[str, Any], access_token: Optional[str] = None, credentials: Optional[Dict[str, Any]] = None) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token")
        handlers = {
            "post_content": self._post_content,
            "manage_comments": self._manage_comments,
            "view_analytics": self._view_analytics,
        }
        handler = handlers.get(action)
        if not handler:
            return ProviderResult(success=False, error=f"Unknown action: {action}")
        try:
            return await handler(parameters, access_token)
        except httpx.HTTPStatusError as exc:
            return ProviderResult(success=False, error=f"Instagram API error {exc.response.status_code}")
        except Exception as exc:
            logger.exception("Instagram provider error")
            return ProviderResult(success=False, error=str(exc))

    async def _post_content(self, params: dict, token: str) -> ProviderResult:
        ig_user_id = params.get("ig_user_id")
        image_url = params.get("image_url")
        caption = params.get("caption", "")
        if not ig_user_id or not image_url:
            return ProviderResult(success=False, error="'ig_user_id' and 'image_url' are required")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GRAPH_API}/{ig_user_id}/media",
                headers=self._headers(token),
                json={"image_url": image_url, "caption": caption},
                timeout=15,
            )
            resp.raise_for_status()
            container = resp.json()
            container_id = container.get("id")
            publish_resp = await client.post(
                f"{GRAPH_API}/{ig_user_id}/media_publish",
                headers=self._headers(token),
                json={"creation_id": container_id},
                timeout=15,
            )
            publish_resp.raise_for_status()
            published = publish_resp.json()
        return ProviderResult(success=True, data={"media_id": published.get("id"), "container_id": container_id})

    async def _manage_comments(self, params: dict, token: str) -> ProviderResult:
        ig_user_id = params.get("ig_user_id")
        media_id = params.get("media_id")
        action_type = params.get("action_type", "list")
        if not ig_user_id:
            return ProviderResult(success=False, error="'ig_user_id' is required")
        async with httpx.AsyncClient() as client:
            if action_type == "list" and media_id:
                resp = await client.get(f"{GRAPH_API}/{media_id}/comments", headers=self._headers(token), timeout=15)
            elif action_type == "reply":
                comment_id = params.get("comment_id")
                text = params.get("text", "")
                resp = await client.post(f"{GRAPH_API}/{comment_id}/replies", headers=self._headers(token), json={"message": text}, timeout=15)
            else:
                return ProviderResult(success=False, error=f"Unknown manage_comments action: {action_type}")
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data=data)

    async def _view_analytics(self, params: dict, token: str) -> ProviderResult:
        ig_user_id = params.get("ig_user_id")
        if not ig_user_id:
            return ProviderResult(success=False, error="'ig_user_id' is required")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GRAPH_API}/{ig_user_id}/insights", headers=self._headers(token), params={"metric": "impressions,reach,profile_views", "period": "day"}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"insights": data.get("data", [])})

    async def test_connection(self, access_token=None, credentials=None) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{GRAPH_API}/me", headers=self._headers(access_token), params={"fields": "id,name"}, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            return ProviderResult(success=True, data={"id": data.get("id"), "name": data.get("name")})
        except Exception as exc:
            return ProviderResult(success=False, error=str(exc))

    async def revoke(self, access_token=None, refresh_token=None, credentials=None) -> ProviderResult:
        return ProviderResult(success=True, metadata={"note": "Instagram tokens are revoked via Meta App Dashboard"})
