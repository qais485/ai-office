"""Gmail Push Notification API — webhook receiver and management endpoints.

Webhook endpoint:
    POST /api/v1/gmail-push/webhook
        Receives Pub/Sub push notifications about Gmail changes.
        No authentication required (validated via Pub/Sub token + shared secret).

Management endpoints (require auth):
    POST /api/v1/gmail-push/watch/{integration_account_id}
        Set up or renew Gmail push notifications for an account.
    POST /api/v1/gmail-push/watch-all
        Set up or renew watches for all active Gmail accounts.
    POST /api/v1/gmail-push/pull
        Pull and process pending Pub/Sub messages (pull mode).
    GET  /api/v1/gmail-push/status
        Get push notification status for current user's Gmail accounts.
"""
import logging
import json
import base64
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.database.session import get_db
from app.api.deps import get_current_active_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ------------------------------------------------------------------
# Webhook endpoint (no auth — validated by Pub/Sub)
# ------------------------------------------------------------------

@router.post("/webhook")
async def gmail_push_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive Gmail push notifications from Cloud Pub/Sub.

    Google Pub/Sub sends a POST request with:
    - Body: Pub/Sub message with base64-encoded data containing
      {"historyId": "...", "emailAddress": "..."}
    - Headers: X-Goog-Signature, X-Goog-Channel-Token (optional)

    Validation:
    1. Verify the request contains valid Pub/Sub message structure.
    2. Verify the shared secret token if GMAIL_WEBHOOK_SECRET is configured.
    3. Process the notification to fetch and handle new messages.
    """
    from app.core.config import settings
    from app.services.gmail_push_service import GmailPushService

    # ── Parse request body ──────────────────────────────────────────
    try:
        body = await request.json()
    except Exception:
        logger.warning("Invalid JSON in Pub/Sub webhook")
        return Response(status_code=400, content="Invalid JSON")

    # ── Validate Pub/Sub message structure ──────────────────────────
    message = body.get("message")
    if not message:
        # Pub/Sub sometimes sends a subscription confirmation
        if body.get("subscription"):
            logger.info("Pub/Sub subscription confirmation received")
            return Response(status_code=200, content="OK")
        logger.warning("Missing message in Pub/Sub payload")
        return Response(status_code=400, content="Missing message")

    # ── Verify shared secret token ──────────────────────────────────
    webhook_secret = getattr(settings, "GMAIL_WEBHOOK_SECRET", "")
    if webhook_secret:
        token = message.get("attributes", {}).get("token", "")
        if not hmac.compare_digest(token, webhook_secret):
            logger.warning(
                "Pub/Sub webhook token mismatch",
                extra={"token_prefix": token[:8] if token else "none"},
            )
            return Response(status_code=403, content="Invalid token")

    # ── Decode message data ─────────────────────────────────────────
    raw_data = message.get("data", "")
    try:
        decoded_data = base64.b64decode(raw_data).decode("utf-8")
        message_data = json.loads(decoded_data)
    except Exception as e:
        logger.warning(f"Failed to decode Pub/Sub message data: {e}")
        return Response(status_code=400, content="Invalid message data")

    history_id = message_data.get("historyId")
    email_address = message_data.get("emailAddress")

    if not history_id:
        logger.warning("Missing historyId in Pub/Sub message")
        return Response(status_code=400, content="Missing historyId")

    logger.info(
        "Gmail push notification received",
        extra={
            "history_id": history_id,
            "email_address": email_address,
            "message_id": message.get("messageId", "unknown"),
        },
    )

    # ── Process the notification ────────────────────────────────────
    push_service = GmailPushService(db)
    result = push_service.process_notification(message_data)

    if result.get("success"):
        logger.info(
            "Gmail push notification processed",
            extra={
                "history_id": history_id,
                "new_emails": result.get("new_emails", 0),
                "processed": result.get("processed", 0),
            },
        )
        return Response(status_code=200, content="OK")
    else:
        logger.error(
            "Failed to process Gmail push notification",
            extra={"history_id": history_id, "error": result.get("error")},
        )
        # Return 200 to prevent Pub/Sub from retrying (we handle our own retries)
        return Response(status_code=200, content="OK")


# ------------------------------------------------------------------
# Management endpoints (require authentication)
# ------------------------------------------------------------------

class WatchSetupRequest(BaseModel):
    webhook_url: Optional[str] = None


@router.post("/watch/{integration_account_id}")
async def setup_gmail_watch(
    integration_account_id: UUID,
    request: WatchSetupRequest = WatchSetupRequest(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Set up or renew Gmail push notifications for a specific account.

    Requires the integration account to be connected and active.
    """
    from app.services.gmail_push_service import GmailPushService
    from app.models.integration_account import IntegrationAccount

    # Verify the account belongs to the current user
    account = db.query(IntegrationAccount).filter(
        IntegrationAccount.id == integration_account_id,
        IntegrationAccount.user_id == current_user.id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Integration account not found")

    push_service = GmailPushService(db)
    result = push_service.setup_watch(
        integration_account_id=integration_account_id,
        webhook_url=request.webhook_url,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Watch setup failed"))

    return {
        "success": True,
        "history_id": result.get("history_id"),
        "expiration": result.get("expiration"),
        "message": "Gmail watch setup complete",
    }


@router.post("/watch-all")
async def setup_all_gmail_watches(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Set up or renew Gmail push notifications for the requesting account's
    active Gmail connections."""
    from app.services.gmail_push_service import GmailPushService

    push_service = GmailPushService(db)
    results = push_service.setup_all_watches(user_id=current_user.id)

    return {
        "success": True,
        "accounts_setup": results.get("success", 0),
        "accounts_failed": results.get("failed", 0),
        "accounts_skipped": results.get("skipped", 0),
    }


@router.post("/pull")
async def pull_pubsub_messages(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Pull and process pending Pub/Sub messages (pull mode).

    Use this endpoint when no public HTTPS endpoint is available.
    Requires GCP_PROJECT_ID and GCS_PUBSUB_SUBSCRIPTION to be configured.
    """
    from app.services.gmail_push_service import GmailPushService

    push_service = GmailPushService(db)
    result = push_service.process_pending_pull_messages()

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Pull failed"))

    return {
        "success": True,
        "messages_pulled": result.get("messages_pulled", 0),
        "processed": result.get("processed", 0),
    }


@router.get("/status")
async def get_push_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get Gmail push notification status for current user's accounts."""
    from app.models.gmail_sync_state import GmailSyncState
    from app.models.integration_account import IntegrationAccount
    from app.models.integration import Integration
    from datetime import datetime, timezone

    # Find Gmail integration
    gmail_integration = db.query(Integration).filter(
        Integration.name == "gmail",
    ).first()

    if not gmail_integration:
        return {"accounts": []}

    # Get user's Gmail accounts
    accounts = db.query(IntegrationAccount).filter(
        IntegrationAccount.integration_id == gmail_integration.id,
        IntegrationAccount.user_id == current_user.id,
        IntegrationAccount.is_active == True,
    ).all()

    result = []
    for account in accounts:
        sync_state = db.query(GmailSyncState).filter(
            GmailSyncState.integration_account_id == account.id,
        ).first()

        push_enabled = False
        watch_expiration = None
        history_id = None

        if sync_state:
            config = sync_state.config or {}
            push_enabled = config.get("push_enabled", False)
            watch_expiration = config.get("watch_expiration")
            history_id = sync_state.gmail_history_id

        # Check if watch is expiring soon
        expiring_soon = False
        if watch_expiration:
            try:
                exp_dt = datetime.fromisoformat(watch_expiration.replace("Z", "+00:00"))
                if exp_dt < datetime.now(timezone.utc) + timedelta(hours=24):
                    expiring_soon = True
            except (ValueError, TypeError):
                pass

        result.append({
            "account_id": str(account.id),
            "display_name": account.display_name,
            "status": account.status,
            "push_enabled": push_enabled,
            "watch_expiration": watch_expiration,
            "expiring_soon": expiring_soon,
            "history_id": history_id,
        })

    return {"accounts": result}


# Missing import
from datetime import timedelta
