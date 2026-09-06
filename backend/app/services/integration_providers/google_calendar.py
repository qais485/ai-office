"""Google Calendar integration provider."""
import logging
from typing import Any, Dict, Optional

import httpx

from app.services.integration_providers.base import IntegrationProvider, ProviderResult

logger = logging.getLogger(__name__)

CAL_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarProvider(IntegrationProvider):
    @property
    def integration_name(self) -> str:
        return "google_calendar"

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def execute_action(self, action: str, parameters: Dict[str, Any], access_token: Optional[str] = None, credentials: Optional[Dict[str, Any]] = None) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token")
        handlers = {
            "read_events": self._read_events,
            "create_event": self._create_event,
            "manage_events": self._manage_events,
        }
        handler = handlers.get(action)
        if not handler:
            return ProviderResult(success=False, error=f"Unknown action: {action}")
        try:
            return await handler(parameters, access_token)
        except httpx.HTTPStatusError as exc:
            return ProviderResult(success=False, error=f"Calendar API error {exc.response.status_code}")
        except Exception as exc:
            logger.exception("GoogleCalendar provider error")
            return ProviderResult(success=False, error=str(exc))

    async def _read_events(self, params: dict, token: str) -> ProviderResult:
        calendar_id = params.get("calendar_id", "primary")
        time_min = params.get("time_min")
        time_max = params.get("time_max")
        max_results = params.get("max_results", 20)
        qp: dict = {"maxResults": max_results, "singleEvents": "true", "orderBy": "startTime"}
        if time_min:
            qp["timeMin"] = time_min
        if time_max:
            qp["timeMax"] = time_max
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{CAL_BASE}/calendars/{calendar_id}/events", headers=self._headers(token), params=qp, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        events = []
        for item in data.get("items", []):
            events.append({
                "id": item.get("id"),
                "summary": item.get("summary", ""),
                "start": item.get("start", {}).get("dateTime", item.get("start", {}).get("date")),
                "end": item.get("end", {}).get("dateTime", item.get("end", {}).get("date")),
                "status": item.get("status"),
                "html_link": item.get("htmlLink"),
            })
        return ProviderResult(success=True, data={"events": events, "total": len(events)})

    async def _create_event(self, params: dict, token: str) -> ProviderResult:
        calendar_id = params.get("calendar_id", "primary")
        summary = params.get("summary", "")
        start = params.get("start")
        end = params.get("end")
        description = params.get("description", "")
        attendees = params.get("attendees", [])
        if not start or not end:
            return ProviderResult(success=False, error="'start' and 'end' are required")
        body: dict = {"summary": summary, "start": {"dateTime": start, "timeZone": "UTC"}, "end": {"dateTime": end, "timeZone": "UTC"}}
        if description:
            body["description"] = description
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{CAL_BASE}/calendars/{calendar_id}/events", headers=self._headers(token), json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"event_id": data.get("id"), "html_link": data.get("htmlLink"), "status": data.get("status")})

    async def _manage_events(self, params: dict, token: str) -> ProviderResult:
        calendar_id = params.get("calendar_id", "primary")
        event_id = params.get("event_id")
        if not event_id:
            return ProviderResult(success=False, error="event_id is required")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{CAL_BASE}/calendars/{calendar_id}/events/{event_id}", headers=self._headers(token), timeout=15)
            resp.raise_for_status()
            data = resp.json()
        return ProviderResult(success=True, data={"id": data.get("id"), "summary": data.get("summary"), "status": data.get("status")})

    async def test_connection(self, access_token=None, credentials=None) -> ProviderResult:
        if not access_token:
            return ProviderResult(success=False, error="No access token")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{CAL_BASE}/users/me/calendarList", headers=self._headers(access_token), params={"maxResults": 1}, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            return ProviderResult(success=True, data={"calendars_count": len(data.get("items", []))})
        except Exception as exc:
            return ProviderResult(success=False, error=str(exc))

    async def revoke(self, access_token=None, refresh_token=None, credentials=None) -> ProviderResult:
        try:
            async with httpx.AsyncClient() as client:
                if access_token:
                    await client.post("https://oauth2.googleapis.com/revoke", params={"token": access_token}, timeout=10)
            return ProviderResult(success=True)
        except Exception:
            logger.warning("Failed to revoke Google Calendar access", exc_info=True)
            return ProviderResult(success=True)
