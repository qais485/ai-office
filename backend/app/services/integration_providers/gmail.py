"""Gmail integration provider – real API calls via Google Gmail REST API."""
import logging
from typing import Any, Dict, Optional

import httpx

from app.services.integration_providers.base import IntegrationProvider, ProviderResult

logger = logging.getLogger(__name__)

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"


class GmailProvider(IntegrationProvider):
    @property
    def integration_name(self) -> str:
        return "gmail"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # execute_action
    # ------------------------------------------------------------------
    async def execute_action(
        self,
        action: str,
        parameters: Dict[str, Any],
        access_token: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token provided")

        handlers = {
            "read_email": self._read_email,
            "search_emails": self._search_emails,
            "list_inboxes": self._list_inboxes,
            "send_email": self._send_email,
            "create_draft": self._create_draft,
            "manage_labels": self._manage_labels,
        }

        handler = handlers.get(action)
        if not handler:
            return ProviderResult(success=False, error=f"Unknown action: {action}")

        try:
            return await handler(parameters, access_token)
        except httpx.HTTPStatusError as exc:
            logger.error("Gmail API error on %s: %s %s", action, exc.response.status_code, exc.response.text[:500])
            return ProviderResult(success=False, error=f"Gmail API error {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            logger.exception("Gmail provider error on %s", action)
            return ProviderResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    async def _read_email(self, params: dict, token: str) -> ProviderResult:
        message_id = params.get("message_id")
        if not message_id:
            return ProviderResult(success=False, error="message_id is required")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GMAIL_BASE}/users/me/messages/{message_id}", headers=self._headers(token), params={"format": "full"}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
        return ProviderResult(success=True, data={
            "id": data.get("id"),
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "snippet": data.get("snippet", ""),
            "label_ids": data.get("labelIds", []),
        })

    async def _search_emails(self, params: dict, token: str) -> ProviderResult:
        query = params.get("query", "")
        max_results = params.get("max_results", 10)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GMAIL_BASE}/users/me/messages",
                headers=self._headers(token),
                params={"q": query, "maxResults": max_results},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        messages = data.get("messages", [])
        return ProviderResult(success=True, data={"messages": messages, "total": data.get("resultSizeEstimate", len(messages))})

    async def _list_inboxes(self, params: dict, token: str) -> ProviderResult:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GMAIL_BASE}/users/me/labels", headers=self._headers(token), timeout=15)
            resp.raise_for_status()
            data = resp.json()
        labels = [{"id": l["id"], "name": l["name"], "type": l.get("type", "")} for l in data.get("labels", [])]
        return ProviderResult(success=True, data={"labels": labels})

    async def _send_email(self, params: dict, token: str) -> ProviderResult:
        to = params.get("to")
        subject = params.get("subject", "")
        body = params.get("body", "")
        if not to:
            return ProviderResult(success=False, error="'to' address is required")
        import base64
        from email.mime.text import MIMEText
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GMAIL_BASE}/users/me/messages/send",
                headers=self._headers(token),
                json={"raw": raw},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"message_id": data.get("id"), "thread_id": data.get("threadId")})

    async def _create_draft(self, params: dict, token: str) -> ProviderResult:
        to = params.get("to", "")
        subject = params.get("subject", "")
        body = params.get("body", "")
        import base64
        from email.mime.text import MIMEText
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GMAIL_BASE}/users/me/drafts",
                headers=self._headers(token),
                json={"message": {"raw": raw}},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"draft_id": data.get("id")})

    async def _manage_labels(self, params: dict, token: str) -> ProviderResult:
        message_id = params.get("message_id")
        add_labels = params.get("add_labels", [])
        remove_labels = params.get("remove_labels", [])
        if not message_id:
            return ProviderResult(success=False, error="message_id is required")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GMAIL_BASE}/users/me/messages/{message_id}/modify",
                headers=self._headers(token),
                json={"addLabelIds": add_labels, "removeLabelIds": remove_labels},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"message_id": data.get("id"), "label_ids": data.get("labelIds", [])})

    # ------------------------------------------------------------------
    # connection test / revoke
    # ------------------------------------------------------------------
    async def test_connection(self, access_token=None, credentials=None) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{GMAIL_BASE}/users/me/profile", headers=self._headers(access_token), timeout=10)
                resp.raise_for_status()
                data = resp.json()
            return ProviderResult(success=True, data={"email": data.get("emailAddress"), "messages_total": data.get("messagesTotal")})
        except Exception as exc:
            return ProviderResult(success=False, error=str(exc))

    async def revoke(self, access_token=None, refresh_token=None, credentials=None) -> ProviderResult:
        try:
            async with httpx.AsyncClient() as client:
                if access_token:
                    await client.post("https://oauth2.googleapis.com/revoke", params={"token": access_token}, timeout=10)
            return ProviderResult(success=True)
        except Exception as exc:
            logger.warning("Gmail revoke failed (best-effort): %s", exc)
            return ProviderResult(success=True, metadata={"revoke_error": str(exc)})
