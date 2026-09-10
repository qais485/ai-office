"""Google Drive integration provider."""
import json
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
            "create_folder": self._create_folder,
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

    @staticmethod
    def _looks_like_drive_query(query: str) -> bool:
        """True when the string already uses Drive's query grammar
        (operators like =, !=, contains, in, has, or quoted values)."""
        lowered = query.lower()
        return any(
            marker in lowered
            for marker in ("=", "!=", "contains", " in ", " has ", "parent in", "mimetype", "'")
        )

    async def _read_files(self, params: dict, token: str) -> ProviderResult:
        query = str(params.get("query") or "").strip()
        # The LLM often sends natural language ("list all folders") — Drive
        # needs its own query grammar and rejects anything else with 400.
        # Translate the common intents; anything that doesn't look like Drive
        # syntax falls back to a name search.
        if query and not self._looks_like_drive_query(query):
            lowered = query.lower()
            if "folder" in lowered or "پوشه" in lowered:
                query = "mimeType='application/vnd.google-apps.folder'"
            else:
                safe = query.replace("\\", "\\\\").replace("'", "\\'")
                query = f"name contains '{safe}'"
        max_results = params.get("max_results", 10)
        qp: dict = {"pageSize": max_results, "fields": "files(id,name,mimeType,modifiedTime,size)"}
        if query:
            qp["q"] = query
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{DRIVE_BASE}/files", headers=self._headers(token), params=qp, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"files": data.get("files", []), "next_page_token": data.get("nextPageToken")})

    async def _resolve_folder_path(self, client: httpx.AsyncClient, token: str, path: str) -> Optional[str]:
        """Resolve a folder NAME (or a/b/c path) to a Drive folder id.
        Missing folders are created along the way — LLMs speak in names,
        not ids. Returns None only on API errors."""
        current_parent = None
        for segment in [s.strip() for s in str(path).split("/") if s.strip()]:
            safe = segment.replace("\\", "\\\\").replace("'", "\\'")
            q = (
                "mimeType='application/vnd.google-apps.folder' "
                f"and name='{safe}' and trashed=false"
            )
            try:
                resp = await client.get(
                    f"{DRIVE_BASE}/files",
                    headers=self._headers(token),
                    params={"q": q, "fields": "files(id,name)", "pageSize": 1},
                    timeout=15,
                )
                resp.raise_for_status()
                files = resp.json().get("files", [])
                if files:
                    current_parent = files[0]["id"]
                    continue
                # Not found — create it (under the walked parent if any)
                metadata: dict = {"name": segment, "mimeType": "application/vnd.google-apps.folder"}
                if current_parent:
                    metadata["parents"] = [current_parent]
                cresp = await client.post(
                    f"{DRIVE_BASE}/files",
                    headers=self._headers(token),
                    json=metadata,
                    timeout=30,
                )
                cresp.raise_for_status()
                current_parent = cresp.json().get("id")
            except httpx.HTTPStatusError:
                return current_parent
        return current_parent

    async def _write_files(self, params: dict, token: str) -> ProviderResult:
        # LLMs send many shapes of the same intent — normalize them all:
        # name / file_name / filename → name; folder / parent → folder NAME
        # (resolved, created if missing); path → "Folder/file.txt" shorthand.
        name = params.get("name") or params.get("file_name") or params.get("filename")
        path = str(params.get("path") or "").strip().strip("/")
        if not name and path and "/" in path:
            name = path.split("/")[-1]
            path = path.rsplit("/", 1)[0]
        if not name:
            name = "Untitled"

        folder_id = params.get("folder_id")
        if not folder_id:
            folder_ref = params.get("folder") or params.get("parent_folder") or path
            if folder_ref:
                async with httpx.AsyncClient() as rclient:
                    folder_id = await self._resolve_folder_path(
                        rclient, token, str(folder_ref)
                    )

        content = params.get("content", "")
        mime_type = params.get("mime_type", "text/plain")
        metadata: dict = {"name": name}
        if folder_id:
            metadata["parents"] = [folder_id]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://www.googleapis.com/upload/drive/v3/files",
                headers={"Authorization": f"Bearer {token}"},
                params={"uploadType": "multipart"},
                files={
                    "metadata": (None, json.dumps(metadata), "application/json"),
                    "file": (name, content.encode(), mime_type),
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"file_id": data.get("id"), "name": data.get("name"), "folder_id": folder_id})

    async def _create_folder(self, params: dict, token: str) -> ProviderResult:
        """Create a Drive folder (a file with the folder mimeType)."""
        name = params.get("name")
        if not name:
            return ProviderResult(success=False, error="'name' is required")
        parent_id = params.get("parent_id") or params.get("folder_id")
        metadata: dict = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            metadata["parents"] = [parent_id]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{DRIVE_BASE}/files",
                headers=self._headers(token),
                json=metadata,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"folder_id": data.get("id"), "name": data.get("name")})

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
