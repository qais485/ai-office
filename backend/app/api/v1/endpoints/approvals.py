from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.approval import ApprovalCreate, ApprovalResponse
from app.services.approval_service import ApprovalService
from app.api.deps import get_current_active_user, require_role
from app.models.user import User, UserRole

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[dict])
def get_approvals(
    status: Optional[str] = None,
    agent_id: Optional[UUID] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ApprovalService(db)
    results = service.get_approvals_with_agents(status=status, agent_id=agent_id, risk_level=risk_level, user_id=current_user.id, role=current_user.role)
    logger.debug("Listed %d approvals for user %s", len(results), current_user.id)
    return results


@router.get("/stats")
def get_approval_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ApprovalService(db)
    return service.get_stats(user_id=current_user.id, role=current_user.role)


@router.get("/{approval_id}", response_model=dict)
def get_approval(
    approval_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ApprovalService(db)
    approval = service.get_approval_with_agent(approval_id, user_id=current_user.id, role=current_user.role)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    logger.debug("Retrieved approval %s for user %s", approval_id, current_user.id)
    return approval


@router.post("/", response_model=ApprovalResponse)
def create_approval(
    approval: ApprovalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify agent ownership
    from app.services.agent_service import AgentService
    agent_service = AgentService(db)
    agent = agent_service.get_agent(approval.agent_id, user_id=current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    service = ApprovalService(db)
    created = service.create_approval(approval)
    logger.info("Created approval %s for user %s", created.id, current_user.id)
    return created


def _ensure_can_decide(db: Session, user: User, approval) -> None:
    """CEO/Admin may decide any approval; the owning user may decide
    approvals raised by their own agents."""
    if user.role in (UserRole.CEO, UserRole.ADMIN):
        return
    from app.models.agent import AIAgent

    agent = db.query(AIAgent).filter(AIAgent.id == approval.agent_id).first()
    if agent is not None and agent.user_id == user.id:
        return
    raise HTTPException(
        status_code=403,
        detail=f"Role '{user.role.value}' is not authorized to decide this approval",
    )


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
def approve_action(
    approval_id: UUID,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ApprovalService(db)
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    _ensure_can_decide(db, current_user, approval)
    decided = service.approve(approval_id, current_user.id, notes)
    if not decided:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    logger.info("Approved action %s by user %s", approval_id, current_user.id)
    return decided


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
def reject_action(
    approval_id: UUID,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ApprovalService(db)
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    _ensure_can_decide(db, current_user, approval)
    decided = service.reject(approval_id, current_user.id, notes)
    if not decided:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    logger.info("Rejected action %s by user %s", approval_id, current_user.id)
    return decided


@router.post("/{approval_id}/cancel", response_model=ApprovalResponse)
def cancel_action(
    approval_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ApprovalService(db)
    approval = service.cancel(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    logger.info("Cancelled approval %s", approval_id)
    return approval


@router.post("/{approval_id}/retry", response_model=ApprovalResponse)
def retry_action(
    approval_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ApprovalService(db)
    approval = service.retry(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found or cannot be retried")
    logger.info("Retried approval %s", approval_id)
    return approval


@router.get("/{approval_id}/events")
def get_approval_events(
    approval_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ApprovalService(db)
    events = service.get_events(approval_id)
    return [
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "old_status": event.old_status,
            "new_status": event.new_status,
            "description": event.description,
            "performed_by": str(event.performed_by) if event.performed_by else None,
            "created_at": event.created_at.isoformat() if event.created_at else None
        }
        for event in events
    ]
