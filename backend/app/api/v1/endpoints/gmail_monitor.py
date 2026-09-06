"""Gmail Monitoring API — manage Gmail sync state and check accounts."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sync-states")
async def list_sync_states(
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List Gmail sync states."""
    from app.models.gmail_sync_state import GmailSyncState

    q = db.query(GmailSyncState)
    if user_id:
        q = q.filter(GmailSyncState.user_id == uuid.UUID(user_id))
    else:
        q = q.filter(GmailSyncState.user_id == current_user.id)

    states = q.all()
    return [_state_to_dict(s) for s in states]


@router.post("/sync-states")
async def create_sync_state(
    integration_account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create or enable a Gmail sync state for an integration account."""
    from app.models.gmail_sync_state import GmailSyncState
    from app.models.integration_account import IntegrationAccount

    account = db.query(IntegrationAccount).filter(
        IntegrationAccount.id == uuid.UUID(integration_account_id),
        IntegrationAccount.user_id == current_user.id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Integration account not found")

    existing = db.query(GmailSyncState).filter(
        GmailSyncState.integration_account_id == uuid.UUID(integration_account_id),
    ).first()

    if existing:
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return _state_to_dict(existing)

    state = GmailSyncState(
        integration_account_id=uuid.UUID(integration_account_id),
        user_id=current_user.id,
        is_active=True,
        processed_message_ids=[],
        total_processed=0,
        consecutive_errors=0,
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return _state_to_dict(state)


@router.put("/sync-states/{state_id}")
async def update_sync_state(
    state_id: str,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a Gmail sync state."""
    from app.models.gmail_sync_state import GmailSyncState

    state = db.query(GmailSyncState).filter(
        GmailSyncState.id == uuid.UUID(state_id),
        GmailSyncState.user_id == current_user.id,
    ).first()

    if not state:
        raise HTTPException(status_code=404, detail="Sync state not found")

    if is_active is not None:
        state.is_active = is_active

    db.commit()
    db.refresh(state)
    return _state_to_dict(state)


@router.delete("/sync-states/{state_id}")
async def delete_sync_state(
    state_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a Gmail sync state."""
    from app.models.gmail_sync_state import GmailSyncState

    state = db.query(GmailSyncState).filter(
        GmailSyncState.id == uuid.UUID(state_id),
        GmailSyncState.user_id == current_user.id,
    ).first()

    if not state:
        raise HTTPException(status_code=404, detail="Sync state not found")

    db.delete(state)
    db.commit()
    return {"success": True, "message": "Sync state deleted"}


@router.post("/check/{integration_account_id}")
async def check_account_now(
    integration_account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Immediately check a Gmail account for new emails."""
    from app.services.gmail_monitor_service import GmailMonitorService
    from app.models.integration_account import IntegrationAccount

    account = db.query(IntegrationAccount).filter(
        IntegrationAccount.id == uuid.UUID(integration_account_id),
        IntegrationAccount.user_id == current_user.id,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Integration account not found")

    monitor = GmailMonitorService(db)
    result = monitor.check_account(uuid.UUID(integration_account_id))
    return result


@router.get("/status")
async def get_gmail_monitor_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get Gmail monitoring status for current user."""
    from app.models.gmail_sync_state import GmailSyncState
    from app.models.integration_account import IntegrationAccount

    states = db.query(GmailSyncState).filter(
        GmailSyncState.user_id == current_user.id,
    ).all()

    return {
        "total_accounts": len(states),
        "active_accounts": sum(1 for s in states if s.is_active),
        "total_processed": sum(s.total_processed or 0 for s in states),
        "accounts": [_state_to_dict(s) for s in states],
    }


def _state_to_dict(state) -> dict:
    return {
        "id": str(state.id),
        "integration_account_id": str(state.integration_account_id),
        "user_id": str(state.user_id),
        "gmail_address": state.gmail_address,
        "gmail_history_id": state.gmail_history_id,
        "messages_total": state.messages_total,
        "is_active": state.is_active,
        "last_sync_at": state.last_sync_at,
        "sync_error": state.sync_error,
        "consecutive_errors": state.consecutive_errors,
        "total_processed": state.total_processed,
        "created_at": state.created_at.isoformat() if state.created_at else None,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }
