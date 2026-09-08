"""Gmail Push Notifications — Cloud Pub/Sub based real-time email detection.

Architecture:
    GmailPushService
        ├── Watches Gmail accounts via Gmail API users.watch()
        ├── Receives Pub/Sub push notifications (webhook) or pulls from Pub/Sub
        ├── Resolves the integration account from the notification
        ├── Fetches changed messages via Gmail API users.history.list()
        ├── Reuses existing GmailMonitorService._process_message for dedup + triggers
        ├── Renews watches before 7-day expiration
        └── Falls back to polling if push delivery fails

Google Cloud Requirements:
    1. A GCP project with Gmail API enabled
    2. A Cloud Pub/Sub topic + subscription
    3. The backend service account must have pubsub.topics.publish permission
    4. A publicly accessible HTTPS endpoint for push delivery (or use pull mode)

External Configuration (all via .env):
    GCP_PROJECT_ID              — GCP project ID
    GCS_PUBSUB_TOPIC            — Pub/Sub topic name (default: "gmail-notifications")
    GCS_PUBSUB_SUBSCRIPTION     — Pub/Sub subscription name (default: "gmail-notifications-sub")
    GMAIL_WEBHOOK_SECRET        — Shared secret for validating Pub/Sub push messages
    GMAIL_PUSH_ENABLED          — Enable/disable push notifications (default: false)
    GMAIL_PUSH_WEBHOOK_URL      — Public HTTPS URL for push delivery
"""
import asyncio
import hashlib
import hmac
import json
import logging
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

# Gmail watch expires after 7 days; renew at 6 days to avoid edge-case gaps.
WATCH_TTL_SECONDS = 6 * 24 * 60 * 60  # 6 days


class GmailPushService:
    """Manages Gmail Push notifications via Cloud Pub/Sub.

    Two operational modes:
        - **Push mode**: GCP Pub/Sub delivers notifications to a webhook endpoint.
        - **Pull mode**: Backend polls Pub/Sub for messages (no public URL needed).

    Both modes use the same ``_process_history_id()`` method to fetch and
    process changed messages, which delegates to the existing
    ``GmailMonitorService._process_message`` pipeline for deduplication and
    trigger creation.
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Watch management
    # ------------------------------------------------------------------

    def setup_watch(
        self,
        integration_account_id: UUID,
        webhook_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call Gmail users.watch() to start receiving push notifications.

        Args:
            integration_account_id: The integration account to watch.
            webhook_url: Public HTTPS URL for Pub/Sub push delivery.
                         Required for push mode; ignored in pull mode.

        Returns:
            Dict with watch result (historyId, expiration, etc.).
        """
        from app.models.integration_account import IntegrationAccount
        from app.models.integration import Integration
        from app.models.gmail_sync_state import GmailSyncState
        from app.services.oauth2_service import OAuth2Service

        account = self.db.query(IntegrationAccount).filter(
            IntegrationAccount.id == integration_account_id,
            IntegrationAccount.is_active == True,
        ).first()

        if not account:
            return {"success": False, "error": "Integration account not found"}

        if account.status != "connected":
            return {"success": False, "error": f"Account status: {account.status}"}

        integration = self.db.query(Integration).filter(
            Integration.id == account.integration_id,
        ).first()

        if not integration or integration.name != "gmail":
            return {"success": False, "error": "Not a Gmail integration"}

        # Get valid token
        oauth2_service = OAuth2Service(self.db)
        from app.utils.async_utils import run_async
        access_token = run_async(self._get_valid_token(account, oauth2_service))
        if not access_token:
            return {"success": False, "error": "Failed to obtain valid access token"}

        # Determine topic name
        from app.core.config import settings
        topic_name = getattr(settings, "GCS_PUBSUB_TOPIC", "gmail-notifications")

        # Call Gmail watch API
        try:
            result = asyncio.run(self._call_watch_api(access_token, topic_name))
        except Exception as e:
            logger.error(
                "Gmail watch setup failed",
                extra={"account_id": str(integration_account_id), "error": str(e)},
                exc_info=True,
            )
            return {"success": False, "error": str(e)}

        if not result.get("success"):
            return result

        # Update sync state with new historyId and expiration
        sync_state = self.db.query(GmailSyncState).filter(
            GmailSyncState.integration_account_id == integration_account_id,
        ).first()

        if not sync_state:
            sync_state = GmailSyncState(
                integration_account_id=integration_account_id,
                user_id=account.user_id,
                is_active=True,
                processed_message_ids=[],
                total_processed=0,
                consecutive_errors=0,
            )
            self.db.add(sync_state)

        sync_state.gmail_history_id = result.get("historyId")
        sync_state.messages_total = result.get("messagesTotal")
        sync_state.last_sync_at = datetime.now(timezone.utc).isoformat()

        # Store watch expiration for renewal scheduling
        if not sync_state.config:
            sync_state.config = {}
        sync_state.config["watch_expiration"] = result.get("expiration")
        sync_state.config["watch_topic"] = topic_name
        sync_state.config["push_enabled"] = True

        self.db.commit()

        logger.info(
            "Gmail watch setup complete",
            extra={
                "account_id": str(integration_account_id),
                "history_id": result.get("historyId"),
                "expiration": result.get("expiration"),
            },
        )

        return {
            "success": True,
            "history_id": result.get("historyId"),
            "expiration": result.get("expiration"),
        }

    def renew_watch(self, integration_account_id: UUID) -> Dict[str, Any]:
        """Renew an expiring Gmail watch. Called by the scheduler before expiration."""
        return self.setup_watch(integration_account_id)

    def setup_all_watches(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Set up or renew watches for the account's active Gmail sync states."""
        from app.models.gmail_sync_state import GmailSyncState

        query = self.db.query(GmailSyncState).filter(
            GmailSyncState.is_active == True,
        )
        if user_id is not None:
            query = query.filter(GmailSyncState.user_id == user_id)
        states = query.all()

        results = {"success": 0, "failed": 0, "skipped": 0}

        for state in states:
            # Check if watch is still valid (not expiring within 1 hour)
            config = state.config or {}
            expiration = config.get("watch_expiration")
            if expiration:
                try:
                    exp_dt = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
                    if exp_dt > datetime.now(timezone.utc) + timedelta(hours=1):
                        results["skipped"] += 1
                        continue
                except (ValueError, TypeError):
                    pass

            result = self.setup_watch(state.integration_account_id)
            if result.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
                logger.warning(
                    "Failed to setup Gmail watch",
                    extra={
                        "account_id": str(state.integration_account_id),
                        "error": result.get("error"),
                    },
                )

        return results

    # ------------------------------------------------------------------
    # Notification processing (called from webhook or pull)
    # ------------------------------------------------------------------

    def process_notification(
        self,
        message_data: Dict[str, Any],
        integration_account_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Process a Pub/Sub notification about Gmail changes.

        Args:
            message_data: The decoded Pub/Sub message data (contains historyId, emailAddress).
            integration_account_id: If known, skip account resolution.

        Returns:
            Dict with processing results.
        """
        history_id = message_data.get("historyId")
        email_address = message_data.get("emailAddress")

        if not history_id:
            return {"success": False, "error": "Missing historyId in notification"}

        # Resolve the integration account
        account = self._resolve_account(email_address, integration_account_id)
        if not account:
            return {"success": False, "error": f"Could not resolve account for {email_address}"}

        # Get valid token
        from app.services.oauth2_service import OAuth2Service
        oauth2_service = OAuth2Service(self.db)
        from app.utils.async_utils import run_async
        access_token = run_async(self._get_valid_token(account, oauth2_service))
        if not access_token:
            return {"success": False, "error": "Failed to obtain valid access token"}

        # Fetch history and process new messages
        try:
            result = asyncio.run(self._process_history_id(
                access_token=access_token,
                account=account,
                new_history_id=history_id,
            ))
            return result
        except Exception as e:
            logger.error(
                "Failed to process Gmail notification",
                extra={
                    "account_id": str(account.id),
                    "history_id": history_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return {"success": False, "error": str(e)}

    def process_pending_pull_messages(self) -> Dict[str, Any]:
        """Pull mode: fetch and process pending Pub/Sub messages.

        Used when no public HTTPS endpoint is available (local development,
        firewalled deployments, etc.).
        """
        from app.core.config import settings
        from app.models.gmail_sync_state import GmailSyncState

        project_id = getattr(settings, "GCP_PROJECT_ID", "")
        subscription = getattr(settings, "GCS_PUBSUB_SUBSCRIPTION", "gmail-notifications-sub")

        if not project_id:
            return {"success": False, "error": "GCP_PROJECT_ID not configured"}

        try:
            result = asyncio.run(self._pull_from_pubsub(project_id, subscription))
            return result
        except Exception as e:
            logger.error(
                "Pub/Sub pull failed",
                extra={"project_id": project_id, "subscription": subscription, "error": str(e)},
                exc_info=True,
            )
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Internal: Gmail API calls
    # ------------------------------------------------------------------

    async def _call_watch_api(self, access_token: str, topic_name: str) -> Dict[str, Any]:
        """Call Gmail users.watch() API."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        from app.core.config import settings
        project_id = getattr(settings, "GCP_PROJECT_ID", "")

        # Full topic resource name
        topic_resource = f"projects/{project_id}/topics/{topic_name}"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GMAIL_BASE}/users/me/watch",
                headers=headers,
                json={
                    "topicName": topic_resource,
                    "labelIds": ["INBOX"],
                    "labelFilterBehavior": "INCLUDE",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                "success": True,
                "historyId": data.get("historyId"),
                "expiration": data.get("expiration"),
                "messagesTotal": data.get("messagesTotal"),
                "threadsTotal": data.get("threadsTotal"),
            }

    async def _process_history_id(
        self,
        access_token: str,
        account,
        new_history_id: str,
    ) -> Dict[str, Any]:
        """Fetch Gmail history since the last known historyId and process new messages."""
        from app.models.gmail_sync_state import GmailSyncState
        from app.services.gmail_monitor_service import GmailMonitorService

        sync_state = self.db.query(GmailSyncState).filter(
            GmailSyncState.integration_account_id == account.id,
        ).first()

        if not sync_state:
            return {"success": False, "error": "No sync state found"}

        old_history_id = sync_state.gmail_history_id

        # If no previous historyId, do a full sync
        if not old_history_id:
            logger.info(
                "No previous historyId, performing full sync",
                extra={"account_id": str(account.id)},
            )
            monitor = GmailMonitorService(self.db)
            result = monitor.check_account(account.id)
            sync_state.gmail_history_id = new_history_id
            self.db.commit()
            return result

        # Fetch history since last known historyId
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        new_message_ids = set()

        async with httpx.AsyncClient() as client:
            page_token = None
            while True:
                params = {
                    "startHistoryId": old_history_id,
                    "historyTypes": ["messageAdded"],
                    "maxResults": 100,
                }
                if page_token:
                    params["pageToken"] = page_token

                try:
                    resp = await client.get(
                        f"{GMAIL_BASE}/users/me/history",
                        headers=headers,
                        params=params,
                        timeout=30,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        # historyId too old; Gmail only keeps ~10 days
                        logger.warning(
                            "Gmail historyId too old, falling back to full sync",
                            extra={"account_id": str(account.id), "old_history_id": old_history_id},
                        )
                        monitor = GmailMonitorService(self.db)
                        result = monitor.check_account(account.id)
                        sync_state.gmail_history_id = new_history_id
                        self.db.commit()
                        return result
                    raise

                # Extract new message IDs from history
                for history in data.get("history", []):
                    for msg_added in history.get("messagesAdded", []):
                        msg = msg_added.get("message", {})
                        msg_id = msg.get("id")
                        if msg_id:
                            # Only include messages with INBOX label
                            label_ids = msg.get("labelIds", [])
                            if "INBOX" in label_ids:
                                new_message_ids.add(msg_id)

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        # Update historyId regardless of whether we found messages
        sync_state.gmail_history_id = new_history_id

        if not new_message_ids:
            sync_state.last_sync_at = datetime.now(timezone.utc).isoformat()
            sync_state.sync_error = None
            sync_state.consecutive_errors = 0
            self.db.commit()
            return {"success": True, "new_emails": 0, "processed": 0}

        # Process each new message using existing pipeline
        monitor = GmailMonitorService(self.db)
        processed_count = 0
        errors = []

        for msg_id in list(new_message_ids)[:20]:  # Rate limit protection
            try:
                # Fetch full message
                msg_detail = await self._fetch_message(client, headers, msg_id)
                if msg_detail:
                    success = await monitor._process_message(msg_detail, account, sync_state)
                    if success:
                        processed_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to process Gmail message {msg_id}: {e}",
                    extra={"account_id": str(account.id)},
                    exc_info=True,
                )
                errors.append(f"{msg_id}: {str(e)}")

        # Update sync state
        sync_state.last_sync_at = datetime.now(timezone.utc).isoformat()
        sync_state.total_processed = (sync_state.total_processed or 0) + processed_count
        sync_state.sync_error = "; ".join(errors) if errors else None
        sync_state.consecutive_errors = 0 if not errors else (sync_state.consecutive_errors or 0)
        self.db.commit()

        logger.info(
            "Gmail push history sync complete",
            extra={
                "account_id": str(account.id),
                "old_history_id": old_history_id,
                "new_history_id": new_history_id,
                "new_messages": len(new_message_ids),
                "processed": processed_count,
                "errors": len(errors),
            },
        )

        return {
            "success": True,
            "new_emails": len(new_message_ids),
            "processed": processed_count,
            "errors": errors,
        }

    async def _fetch_message(self, client, headers: dict, message_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full message details from Gmail API."""
        try:
            resp = await client.get(
                f"{GMAIL_BASE}/users/me/messages/{message_id}",
                headers=headers,
                params={"format": "full"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            headers_map = {}
            for h in data.get("payload", {}).get("headers", []):
                headers_map[h["name"]] = h["value"]

            return {
                "id": data.get("id"),
                "thread_id": data.get("threadId"),
                "subject": headers_map.get("Subject", ""),
                "from": headers_map.get("From", ""),
                "to": headers_map.get("To", ""),
                "date": headers_map.get("Date", ""),
                "snippet": data.get("snippet", ""),
                "label_ids": data.get("labelIds", []),
                "body": self._extract_body(data.get("payload", {})),
            }
        except Exception as e:
            logger.error(f"Failed to fetch Gmail message {message_id}: {e}", exc_info=True)
            return None

    def _extract_body(self, payload: dict) -> str:
        """Extract text body from Gmail message payload."""
        body = ""

        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        elif payload.get("parts"):
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                    break
                elif part.get("parts"):
                    nested = self._extract_body(part)
                    if nested:
                        body = nested
                        break

        return body[:10000]

    # ------------------------------------------------------------------
    # Internal: Pub/Sub pull
    # ------------------------------------------------------------------

    async def _pull_from_pubsub(self, project_id: str, subscription: str) -> Dict[str, Any]:
        """Pull messages from a Pub/Sub subscription.

        Uses the Pub/Sub REST API with Application Default Credentials
        or a service account key.
        """
        subscription_resource = f"projects/{project_id}/subscriptions/{subscription}"

        # Get access token for Pub/Sub API
        # This uses Application Default Credentials or the GCP service account
        import subprocess
        try:
            result = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True, text=True, timeout=10,
            )
            access_token = result.stdout.strip()
        except Exception:
            # Fallback: try to use the Google Auth library
            try:
                import google.auth
                import google.auth.transport.requests
                creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/pubsub"])
                creds.refresh(google.auth.transport.requests.Request())
                access_token = creds.token
            except Exception as e:
                return {"success": False, "error": f"Failed to get Pub/Sub credentials: {e}"}

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        processed_count = 0
        ack_ids = []

        async with httpx.AsyncClient() as client:
            # Pull messages (max 100, return immediately)
            resp = await client.post(
                f"https://pubsub.googleapis.com/v1/{subscription_resource}:pull",
                headers=headers,
                json={
                    "returnImmediately": True,
                    "maxMessages": 100,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            received_messages = data.get("receivedMessages", [])

            for msg in received_messages:
                message = msg.get("message", {})
                ack_id = msg.get("ackId")

                # Decode the message data
                raw_data = message.get("data", "")
                try:
                    decoded_data = base64.b64decode(raw_data).decode("utf-8")
                    message_data = json.loads(decoded_data)
                except Exception as e:
                    logger.warning(f"Failed to decode Pub/Sub message: {e}")
                    if ack_id:
                        ack_ids.append(ack_id)
                    continue

                # Process the notification
                result = self.process_notification(message_data)
                if result.get("success"):
                    processed_count += 1

                if ack_id:
                    ack_ids.append(ack_id)

            # Acknowledge processed messages
            if ack_ids:
                try:
                    await client.post(
                        f"https://pubsub.googleapis.com/v1/{subscription_resource}:acknowledge",
                        headers=headers,
                        json={"ackIds": ack_ids},
                        timeout=30,
                    )
                except Exception as e:
                    logger.warning(f"Failed to acknowledge Pub/Sub messages: {e}")

        return {
            "success": True,
            "messages_pulled": len(received_messages),
            "processed": processed_count,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_account(
        self,
        email_address: Optional[str],
        integration_account_id: Optional[UUID] = None,
    ) -> Optional[Any]:
        """Resolve an integration account from email address or explicit ID."""
        from app.models.integration_account import IntegrationAccount
        from app.models.integration import Integration

        if integration_account_id:
            account = self.db.query(IntegrationAccount).filter(
                IntegrationAccount.id == integration_account_id,
                IntegrationAccount.is_active == True,
            ).first()
            if account:
                return account

        if not email_address:
            return None

        # Find Gmail integration
        gmail_integration = self.db.query(Integration).filter(
            Integration.name == "gmail",
        ).first()
        if not gmail_integration:
            return None

        # Search integration_accounts for matching email
        # The display_name or config may contain the email address
        accounts = self.db.query(IntegrationAccount).filter(
            IntegrationAccount.integration_id == gmail_integration.id,
            IntegrationAccount.is_active == True,
            IntegrationAccount.status == "connected",
        ).all()

        for account in accounts:
            # Check display_name
            if account.display_name and email_address.lower() in account.display_name.lower():
                return account
            # Check config
            config = account.config or {}
            if config.get("email_address", "").lower() == email_address.lower():
                return account

        return None

    async def _get_valid_token(self, account, oauth2_service) -> Optional[str]:
        """Get a valid access token, refreshing if necessary (async)."""
        try:
            if account.oauth2_token_expiry:
                try:
                    expiry = datetime.fromisoformat(account.oauth2_token_expiry)
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > expiry:
                        logger.info("Gmail access token expired, refreshing")
                        refreshed = await oauth2_service.refresh_access_token(account)
                        if refreshed:
                            return refreshed
                        logger.warning("Gmail token refresh failed")
                        return None
                except (ValueError, TypeError):
                    pass

            return oauth2_service.get_access_token(account)
        except Exception as e:
            logger.error(f"Failed to get Gmail access token: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Watch renewal scheduler job
    # ------------------------------------------------------------------

    async def check_and_renew_watches(self) -> None:
        """Scheduler job: renew watches that are expiring within 24 hours."""
        from app.models.gmail_sync_state import GmailSyncState

        states = self.db.query(GmailSyncState).filter(
            GmailSyncState.is_active == True,
        ).all()

        for state in states:
            config = state.config or {}
            if not config.get("push_enabled"):
                continue

            expiration = config.get("watch_expiration")
            if not expiration:
                continue

            try:
                exp_dt = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)

                # Renew if expiring within 24 hours
                if exp_dt - now < timedelta(hours=24):
                    logger.info(
                        "Renewing expiring Gmail watch",
                        extra={
                            "account_id": str(state.integration_account_id),
                            "expires_at": expiration,
                        },
                    )
                    result = self.renew_watch(state.integration_account_id)
                    if not result.get("success"):
                        logger.error(
                            "Failed to renew Gmail watch",
                            extra={
                                "account_id": str(state.integration_account_id),
                                "error": result.get("error"),
                            },
                        )
            except (ValueError, TypeError):
                pass


# Global singleton for convenience
def get_gmail_push_service(db: Session) -> GmailPushService:
    """Get a GmailPushService instance."""
    return GmailPushService(db)
