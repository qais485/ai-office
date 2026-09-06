"""Gmail Monitor Service — polls Gmail API for new emails and fires triggers.

Architecture:
    GmailMonitorService (singleton)
        ├── Polls connected Gmail accounts via Gmail API
        ├── Deduplicates using processed_message_ids
        ├── Creates EMAIL_RECEIVED events
        ├── Finds agents with gmail integration triggers
        └── Fires AgentTriggers for matching agents

Key principles:
    - Uses Gmail API (not IMAP) for OAuth2-authenticated access
    - Configurable polling interval per account
    - Handles token refresh automatically
    - Prevents duplicate processing via message ID tracking
    - Non-blocking async execution
    - Structured logging with execution tracing
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

# Backoff settings for API errors
MAX_BACKOFF_SECONDS = 300
BASE_BACKOFF_SECONDS = 5
MAX_CONSECUTIVE_ERRORS = 5


class GmailMonitorService:
    """Polls Gmail API for new emails and fires agent triggers."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Main polling entry point
    # ------------------------------------------------------------------

    def check_account(self, integration_account_id: UUID) -> Dict[str, Any]:
        """Check a single Gmail account for new emails.

        This is the main entry point called by the background worker.
        Returns a summary of what was found/processed.
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

        # Get or create sync state
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
            self.db.commit()
            self.db.refresh(sync_state)

        if not sync_state.is_active:
            return {"success": False, "error": "Sync is disabled for this account"}

        # Check backoff — circuit breaker WITH recovery: pause for 10 minutes
        # after too many errors, then automatically retry (old code paused
        # forever and never recovered).
        if (sync_state.consecutive_errors or 0) >= MAX_CONSECUTIVE_ERRORS:
            last_attempt = None
            if sync_state.last_sync_at:
                try:
                    last_attempt = datetime.fromisoformat(sync_state.last_sync_at)
                    if last_attempt.tzinfo is None:
                        last_attempt = last_attempt.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    last_attempt = None
            if last_attempt and (datetime.now(timezone.utc) - last_attempt).total_seconds() < 600:
                return {"success": False, "error": "Too many consecutive errors, sync paused (10 min backoff)"}
            # Recovery window elapsed — clear the breaker and try again
            logger.info(
                "Gmail sync circuit breaker recovery: retrying after backoff",
                extra={"account_id": str(integration_account_id)},
            )
            sync_state.consecutive_errors = 0

        # Get valid access token + fetch — inside one event loop so the async
        # token refresh is properly awaited.
        oauth2_service = OAuth2Service(self.db)

        async def _run_check():
            access_token = await self._get_valid_token(account, oauth2_service)
            if not access_token:
                sync_state.sync_error = "Failed to obtain valid access token"
                self.db.commit()
                return {"success": False, "error": "Failed to obtain valid access token"}
            return await self._fetch_and_process(
                access_token=access_token,
                sync_state=sync_state,
                account=account,
            )

        try:
            result = asyncio.run(_run_check())
            return result
        except Exception as e:
            logger.error(
                "Gmail check failed",
                extra={"account_id": str(integration_account_id), "error": str(e)},
                exc_info=True,
            )
            sync_state.sync_error = str(e)[:500]
            sync_state.consecutive_errors = (sync_state.consecutive_errors or 0) + 1
            self.db.commit()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    async def _get_valid_token(self, account, oauth2_service) -> Optional[str]:
        """Get a valid access token, refreshing if necessary (async — the
        refresh call hits Google's token endpoint)."""
        try:
            # Check if token is expired
            if account.oauth2_token_expiry:
                try:
                    expiry = datetime.fromisoformat(account.oauth2_token_expiry)
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > expiry:
                        # Token expired, refresh
                        logger.info("Gmail access token expired, refreshing")
                        refreshed = await oauth2_service.refresh_access_token(account)
                        if refreshed:
                            return refreshed
                        logger.warning("Gmail token refresh failed")
                        return None
                except (ValueError, TypeError):
                    pass

            # Token not expired or no expiry set, try to use it
            return oauth2_service.get_access_token(account)
        except Exception as e:
            logger.error(f"Failed to get Gmail access token: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Gmail API polling
    # ------------------------------------------------------------------

    async def _fetch_and_process(
        self,
        access_token: str,
        sync_state,
        account,
    ) -> Dict[str, Any]:
        """Fetch messages from Gmail API and process new ones."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Query for unread messages not in processed list
        query = "is:unread -label:processed"
        processed_ids = set(sync_state.processed_message_ids or [])

        new_messages = []
        page_token = None

        async with httpx.AsyncClient() as client:
            # Fetch message list
            while True:
                params = {"q": query, "maxResults": 50}
                if page_token:
                    params["pageToken"] = page_token

                try:
                    resp = await client.get(
                        f"{GMAIL_BASE}/users/me/messages",
                        headers=headers,
                        params=params,
                        timeout=15,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        logger.warning("Gmail API 401 - token may be revoked")
                        # Persist the failure so the UI/database reflect it instead
                        # of silently retrying with a dead token forever.
                        sync_state.sync_error = "Gmail token revoked or invalid — reconnect the account"
                        sync_state.consecutive_errors = (sync_state.consecutive_errors or 0) + 1
                        self.db.commit()
                        return {"success": False, "error": "Token revoked or invalid"}
                    raise

                messages = data.get("messages", [])
                for msg in messages:
                    msg_id = msg.get("id")
                    if msg_id and msg_id not in processed_ids:
                        new_messages.append(msg)

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        if not new_messages:
            # Update sync state
            sync_state.last_sync_at = datetime.now(timezone.utc).isoformat()
            sync_state.sync_error = None
            sync_state.consecutive_errors = 0
            self.db.commit()
            return {"success": True, "new_emails": 0, "processed": 0}

        # Process each new message
        # NOTE: the client used for the message-list query above has been closed
        # by now, so open a fresh client for the per-message detail fetches.
        processed_count = 0
        errors = []

        async with httpx.AsyncClient() as client:
            for msg_info in new_messages[:20]:  # Limit to 20 per sync to avoid rate limits
                msg_id = msg_info.get("id")
                try:
                    # Fetch full message details
                    msg_detail = await self._fetch_message(client, headers, msg_id)
                    if msg_detail:
                        # Process and create trigger
                        success = await self._process_message(msg_detail, account, sync_state)
                        if success:
                            processed_count += 1
                            processed_ids.add(msg_id)
                        else:
                            errors.append(f"Failed to process {msg_id}")
                except Exception as e:
                    logger.error(f"Failed to process Gmail message {msg_id}: {e}", exc_info=True)
                    errors.append(f"{msg_id}: {str(e)}")

        # Update sync state
        # Keep only last 1000 message IDs to prevent unbounded growth
        recent_ids = list(processed_ids)[-1000:]
        sync_state.processed_message_ids = recent_ids
        sync_state.total_processed = (sync_state.total_processed or 0) + processed_count
        sync_state.last_sync_at = datetime.now(timezone.utc).isoformat()
        sync_state.sync_error = "; ".join(errors) if errors else None
        sync_state.consecutive_errors = 0 if not errors else (sync_state.consecutive_errors or 0)
        self.db.commit()

        logger.info(
            "Gmail sync complete",
            extra={
                "account_id": str(account.id),
                "new_found": len(new_messages),
                "processed": processed_count,
                "errors": len(errors),
            },
        )

        return {
            "success": True,
            "new_emails": len(new_messages),
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

            # Extract headers
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
            import base64
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        elif payload.get("parts"):
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                    import base64
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                    break
                elif part.get("parts"):
                    # Recurse into nested parts
                    nested = self._extract_body(part)
                    if nested:
                        body = nested
                        break

        return body[:10000]  # Limit body size

    # ------------------------------------------------------------------
    # Message processing and trigger creation
    # ------------------------------------------------------------------

    async def _process_message(
        self,
        message: Dict[str, Any],
        account,
        sync_state,
    ) -> bool:
        """Process a single Gmail message: create event and fire triggers.

        Uses ``GmailDeduplicationService`` for durable idempotency instead of
        ad-hoc in-memory checks.
        """
        from app.events.types import EventType, EmailEvent
        from app.events.bus import event_bus
        from app.services.trigger_service import TriggerService
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome
        from app.models.agent import AIAgent, LifecycleStatus
        from app.models.agent_integration import AgentIntegration
        from app.models.integration import Integration

        msg_id = message.get("id", "")
        from_addr = message.get("from", "")
        subject = message.get("subject", "")

        # Parse from address
        from_address = from_addr
        if "<" in from_addr and ">" in from_addr:
            from_address = from_addr.split("<")[1].split(">")[0]

        # Mirror into email_messages so the Email Dashboard shows Gmail history
        self._mirror_message_to_email_messages(message, account, from_address)

        # Find the Gmail integration
        gmail_integration = self.db.query(Integration).filter(
            Integration.name == "gmail",
        ).first()
        if not gmail_integration:
            logger.warning("Gmail integration not found in database")
            return False

        # Find agents linked to Gmail integration
        agent_links = self.db.query(AgentIntegration).filter(
            AgentIntegration.integration_id == gmail_integration.id,
            AgentIntegration.is_active == True,
        ).all()

        if not agent_links:
            logger.debug("No agents linked to Gmail integration")
            return False

        trigger_service = TriggerService(self.db)
        dedup = GmailDeduplicationService(self.db)
        triggers_created = 0

        for link in agent_links:
            agent = self.db.query(AIAgent).filter(
                AIAgent.id == link.agent_id,
                AIAgent.lifecycle_status == LifecycleStatus.ACTIVE,
            ).first()

            if not agent:
                continue

            # ── Durable deduplication check ───────────────────────────
            outcome = dedup.claim(
                integration_account_id=account.id,
                gmail_message_id=msg_id,
                agent_id=agent.id,
                event_type="email_received",
            )

            if outcome == DedupOutcome.ALREADY_COMPLETED:
                dedup.increment_duplicate(
                    integration_account_id=account.id,
                    gmail_message_id=msg_id,
                    agent_id=agent.id,
                )
                logger.debug(
                    "Gmail event already completed for agent, skipping",
                    extra={"agent_id": str(agent.id), "message_id": msg_id},
                )
                continue

            if outcome == DedupOutcome.PROCESSING:
                dedup.increment_duplicate(
                    integration_account_id=account.id,
                    gmail_message_id=msg_id,
                    agent_id=agent.id,
                )
                logger.debug(
                    "Gmail event currently processing for agent, skipping",
                    extra={"agent_id": str(agent.id), "message_id": msg_id},
                )
                continue

            if outcome == DedupOutcome.REJECTED:
                dedup.increment_duplicate(
                    integration_account_id=account.id,
                    gmail_message_id=msg_id,
                    agent_id=agent.id,
                )
                logger.debug(
                    "Gmail event rejected (max retries exhausted) for agent",
                    extra={"agent_id": str(agent.id), "message_id": msg_id},
                )
                continue

            # outcome is CLAIMED or RETRY_ELIGIBLE — proceed with processing

            # ── Create trigger ─────────────────────────────────────────
            trigger = None
            try:
                trigger = trigger_service.fire_integration_trigger(
                    agent_id=agent.id,
                    integration_name="gmail",
                    event_type="email_received",
                    event_id=msg_id,
                    payload={
                        "email_id": msg_id,
                        "from_address": from_address,
                        "subject": subject,
                        "snippet": message.get("snippet", ""),
                        "date": message.get("date", ""),
                        "label_ids": message.get("label_ids", []),
                        "body_preview": message.get("body", "")[:500],
                        "account_id": str(account.id),
                    },
                )

                if trigger:
                    triggers_created += 1
                    dedup.mark_completed(
                        integration_account_id=account.id,
                        gmail_message_id=msg_id,
                        agent_id=agent.id,
                        trigger_id=trigger.id,
                    )
                    logger.info(
                        "Gmail trigger created",
                        extra={
                            "agent_id": str(agent.id),
                            "agent_name": agent.name,
                            "trigger_id": str(trigger.id),
                            "message_id": msg_id,
                            "subject": subject,
                            "outcome": outcome.value,
                        },
                    )
                else:
                    # Trigger creation returned None (e.g. cooldown).
                    # Mark as completed to avoid infinite retries for this cause.
                    dedup.mark_completed(
                        integration_account_id=account.id,
                        gmail_message_id=msg_id,
                        agent_id=agent.id,
                    )

            except Exception as e:
                dedup.mark_failed(
                    integration_account_id=account.id,
                    gmail_message_id=msg_id,
                    agent_id=agent.id,
                    error_message=str(e),
                )
                logger.error(
                    "Failed to create Gmail trigger",
                    extra={"agent_id": str(agent.id), "message_id": msg_id, "error": str(e)},
                    exc_info=True,
                )

        # Also publish EMAIL_RECEIVED event for any other handlers
        try:
            event = EmailEvent(
                email_id=msg_id,
                from_address=from_address,
                subject=subject,
                account_id=str(account.id),
            )
            await event_bus.publish(event)
        except Exception as e:
            logger.warning(f"Failed to publish EMAIL_RECEIVED event: {e}", exc_info=True)

        # Add label to mark as processed
        await self._add_processed_label(access_token=None, message_id=msg_id, account=account)

        return triggers_created > 0

    def _mirror_message_to_email_messages(self, message: Dict[str, Any], account, from_address: str) -> None:
        """Persist a Gmail message into email_messages so the Email Dashboard
        shows the Gmail account history too (the agent-trigger path does not
        populate that table on its own)."""
        from app.models.email import EmailMessage, EmailStatus

        msg_id = message.get("id", "")
        try:
            existing = self.db.query(EmailMessage).filter(
                EmailMessage.conversation_id == msg_id,
                EmailMessage.account_id.is_(None),
                EmailMessage.category == "gmail",
            ).first()
            if existing:
                return

            self.db.add(EmailMessage(
                from_address=from_address or "(unknown)",
                to_address=message.get("to") or "(gmail inbox)",
                subject=message.get("subject") or "(no subject)",
                body=message.get("body") or message.get("snippet") or "",
                status=EmailStatus.NEW,
                conversation_id=msg_id,
                category="gmail",
                account_id=None,
            ))
            self.db.commit()
            logger.debug("Mirrored Gmail message to email_messages", extra={"message_id": msg_id})
        except Exception as e:
            self.db.rollback()
            logger.warning(f"Failed to mirror Gmail message {msg_id} to email_messages: {e}", exc_info=True)

    async def _add_processed_label(self, access_token: Optional[str], message_id: str, account) -> None:
        """Add a label to mark the message as processed."""
        if not access_token:
            from app.services.oauth2_service import OAuth2Service
            oauth2_service = OAuth2Service(self.db)
            access_token = await self._get_valid_token(account, oauth2_service)

        if not access_token:
            return

        try:
            # Find or create "Processed" label
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

            async with httpx.AsyncClient() as client:
                # List labels to find "Processed"
                resp = await client.get(f"{GMAIL_BASE}/users/me/labels", headers=headers, timeout=10)
                resp.raise_for_status()
                labels = resp.json().get("labels", [])

                processed_label_id = None
                for label in labels:
                    if label.get("name") == "Processed":
                        processed_label_id = label.get("id")
                        break

                # Create label if not found
                if not processed_label_id:
                    resp = await client.post(
                        f"{GMAIL_BASE}/users/me/labels",
                        headers=headers,
                        json={"name": "Processed", "labelListVisibility": "labelHide", "messageListVisibility": "hide"},
                        timeout=10,
                    )
                    resp.raise_for_status()
                    processed_label_id = resp.json().get("id")

                if processed_label_id:
                    # Add label to message
                    await client.post(
                        f"{GMAIL_BASE}/users/me/messages/{message_id}/modify",
                        headers=headers,
                        json={"addLabelIds": [processed_label_id]},
                        timeout=10,
                    )
        except Exception as e:
            logger.warning(f"Failed to add processed label to Gmail message: {e}", exc_info=True)


# ------------------------------------------------------------------
# Background worker function
# ------------------------------------------------------------------

async def poll_gmail_accounts():
    """Background Gmail polling loop. Checks connected Gmail accounts."""
    logger.info("Gmail monitoring loop started")

    while True:
        try:
            from app.database.session import SessionLocal
            from app.models.gmail_sync_state import GmailSyncState

            db = SessionLocal()
            try:
                # Find accounts that need checking
                now = datetime.now(timezone.utc)
                active_states = db.query(GmailSyncState).filter(
                    GmailSyncState.is_active == True,
                ).all()

                for state in active_states:
                    # Check if it's time to sync (every 60 seconds minimum)
                    if state.last_sync_at:
                        try:
                            last_sync = datetime.fromisoformat(state.last_sync_at)
                            if last_sync.tzinfo is None:
                                last_sync = last_sync.replace(tzinfo=timezone.utc)
                            if (now - last_sync).total_seconds() < 60:
                                continue
                        except (ValueError, TypeError):
                            pass

                    # Check account
                    try:
                        monitor = GmailMonitorService(db)
                        result = monitor.check_account(state.integration_account_id)
                        if result.get("new_emails", 0) > 0:
                            logger.info(
                                f"Gmail: {result['new_emails']} new emails found, {result.get('processed', 0)} processed"
                            )
                    except Exception as e:
                        logger.error(
                            f"Gmail check failed for account {state.integration_account_id}: {e}",
                            exc_info=True,
                        )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Gmail monitoring error: {e}", exc_info=True)

        await asyncio.sleep(30)


# ------------------------------------------------------------------
# Single-pass function for the scheduler
# ------------------------------------------------------------------

async def check_all_gmail_accounts():
    """Single Gmail check pass — called by the scheduler.

    Includes retry logic for transient database errors (Neon SSL EOF).
    """
    from app.database.session import SessionLocal
    from app.database.retry import db_retry
    from app.models.gmail_sync_state import GmailSyncState

    @db_retry(max_retries=2, base_delay=1.0)
    def _check():
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)

            # Self-healing: ensure every connected Gmail integration account has a
            # sync state. Accounts connected before the auto-create logic existed
            # (or whose OAuth callback failed midway) would otherwise be invisible
            # to the monitor forever, because the monitor only iterates sync states.
            from app.models.integration import Integration
            from app.models.integration_account import IntegrationAccount

            accounts_without_state = (
                db.query(IntegrationAccount)
                .join(Integration, Integration.id == IntegrationAccount.integration_id)
                .outerjoin(GmailSyncState, GmailSyncState.integration_account_id == IntegrationAccount.id)
                .filter(
                    Integration.name == "gmail",
                    IntegrationAccount.is_active == True,
                    IntegrationAccount.status == "connected",
                    GmailSyncState.id.is_(None),
                )
                .all()
            )
            for orphan_account in accounts_without_state:
                db.add(GmailSyncState(
                    integration_account_id=orphan_account.id,
                    user_id=orphan_account.user_id,
                    is_active=True,
                    processed_message_ids=[],
                    total_processed=0,
                    consecutive_errors=0,
                ))
                logger.warning(
                    "Created missing GmailSyncState for connected Gmail account",
                    extra={"integration_account_id": str(orphan_account.id)},
                )
            if accounts_without_state:
                db.commit()

            active_states = db.query(GmailSyncState).filter(
                GmailSyncState.is_active == True,
            ).all()

            for state in active_states:
                # Respect minimum 60-second interval between syncs per account
                if state.last_sync_at:
                    try:
                        last_sync = datetime.fromisoformat(state.last_sync_at)
                        if last_sync.tzinfo is None:
                            last_sync = last_sync.replace(tzinfo=timezone.utc)
                        if (now - last_sync).total_seconds() < 60:
                            continue
                    except (ValueError, TypeError):
                        pass

                try:
                    monitor = GmailMonitorService(db)
                    result = monitor.check_account(state.integration_account_id)
                    if result.get("new_emails", 0) > 0:
                        logger.info(
                            f"Gmail: {result['new_emails']} new emails found, {result.get('processed', 0)} processed"
                        )
                except Exception as e:
                    logger.error(
                        f"Gmail check failed for account {state.integration_account_id}: {e}",
                        exc_info=True,
                    )
        finally:
            db.close()

    try:
        await asyncio.to_thread(_check)
    except Exception as e:
        logger.error(f"Gmail monitoring error after retries: {e}", exc_info=True)
