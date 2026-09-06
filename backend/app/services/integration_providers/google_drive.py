"""Google Drive integration provider."""
import logging
from typing import Any, Dict, Optional

import httpx

from app.services.integration_providers.base import IntegrationProvider, ProviderResult

logger = logging.getLogger(__name__)

DRIVE_BASE = "https://www.googleapis.com/drive/v3"


class GoogleDriveProvider(IntegrationProvider):
    @property
    def integration_name(self) -> str:
        return "google_drive"

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def execute_action(self, action: str, parameters: Dict[str, Any], access_token: Optional[str] = None, credentials: Optional[Dict[str, Any]] = None) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token")
        handlers = {
            "read_files": self._read_files,
            "write_files": self._write_files,
            "share_files": self._share_files,
        }
        handler = handlers.get(action)
        if not handler:
            return ProviderResult(success=False, error=f"Unknown action: {action}")
        try:
            return await handler(parameters, access_token)
        except httpx.HTTPStatusError as exc:
            return ProviderResult(success=False, error=f"Drive API error {exc.response.status_code}")
        except Exception as exc:
            logger.exception("GoogleDrive provider error")
            return ProviderResult(success=False, error=str(exc))

    async def _read_files(self, params: dict, token: str) -> ProviderResult:
        query = params.get("query", "")
        max_results = params.get("max_results", 10)
        qp: dict = {"pageSize": max_results, "fields": "files(id,name,mimeType,modifiedTime,size)"}
        if query:
            qp["q"] = query
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{DRIVE_BASE}/files", headers=self._headers(token), params=qp, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"files": data.get("files", []), "next_page_token": data.get("nextPageToken")})

    async def _write_files(self, params: dict, token: str) -> ProviderResult:
        name = params.get("name", "Untitled")
        content = params.get("content", "")
        mime_type = params.get("mime_type", "text/plain")
        folder_id = params.get("folder_id")
        import io
        metadata: dict = {"name": name}
        if folder_id:
            metadata["parents"] = [folder_id]
        files_metadata = httpx.Response(200, json=metadata)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://www.googleapis.com/upload/drive/v3/files",
                headers={"Authorization": f"Bearer {token}"},
                params={"uploadType": "multipart"},
                files={
                    "metadata": (None, str(metadata), "application/json"),
                    "file": (name, content.encode(), mime_type),
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"file_id": data.get("id"), "name": data.get("name")})

    async def _share_files(self, params: dict, token: str) -> ProviderResult:
        file_id = params.get("file_id")
        email = params.get("email")
        role = params.get("role", "reader")
        if not file_id or not email:
            return ProviderResult(success=False, error="file_id and email are required")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{DRIVE_BASE}/files/{file_id}/permissions",
                headers=self._headers(token),
                json={"type": "user", "role": role, "emailAddress": email},
                params={"sendNotificationEmail": "true"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"permission_id": data.get("id")})

    async def test_connection(self, access_token=None, credentials=None) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{DRIVE_BASE}/about", headers=self._headers(access_token), params={"fields": "user"}, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            return ProviderResult(success=True, data={"user": data.get("user", {}).get("displayName")})
        except Exception as exc:
            return ProviderResult(success=False, error=str(exc))

    async def revoke(self, access_token=None, refresh_token=None, credentials=None) -> ProviderResult:
        try:
            async with httpx.AsyncClient() as client:
                if access_token:
                    await client.post("https://oauth2.googleapis.com/revoke", params={"token": access_token}, timeout=10)
            return ProviderResult(success=True)
        except Exception:
            logger.warning("Failed to revoke Google Drive access", exc_info=True)
            return ProviderResult(success=True)
