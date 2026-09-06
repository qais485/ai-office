from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.services.tool_execution_service import ToolExecutionService
from app.services.approval_service import ApprovalService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ExecuteToolRequest(BaseModel):
    agent_id: UUID
    tool_name: str
    action: str
    parameters: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class ApproveRequest(BaseModel):
    notes: Optional[str] = None


class RejectRequest(BaseModel):
    notes: Optional[str] = None


@router.post("/execute")
async def execute_tool(request: ExecuteToolRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = ToolExecutionService(db)
    result = service.execute_tool(
        agent_id=request.agent_id,
        tool_name=request.tool_name,
        action=request.action,
        parameters=request.parameters,
        reason=request.reason,
        user_id=current_user.id
    )
    
    if not result["success"] and not result.get("requires_approval"):
        logger.error("Tool execution failed for agent %s: %s", request.agent_id, result["error"])
        raise HTTPException(status_code=400, detail=result["error"])
    
    logger.info("Tool %s executed by agent %s (action=%s)", request.tool_name, request.agent_id, request.action)
    return result


@router.get("/pending-approvals")
async def get_pending_approvals(limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = ToolExecutionService(db)
    approvals = service.get_pending_approvals(limit=limit)
    return [
        {
            "id": str(a.id),
            "agent_id": str(a.agent_id),
            "action": a.action,
            "parameters": a.parameters,
            "reason": a.reason,
            "risk_level": a.risk_level,
            "status": a.status,
            "requested_at": a.requested_at,
            "created_at": str(a.created_at)
        }
        for a in approvals
    ]


@router.get("/approval-stats")
async def get_approval_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = ToolExecutionService(db)
    return service.get_approval_stats()


@router.post("/{approval_id}/approve")
async def approve_action(approval_id: UUID, request: ApproveRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = ApprovalService(db)
    approval = service.approve(approval_id, current_user.id, request.notes)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    logger.info("Approved tool execution %s by user %s", approval_id, current_user.id)
    return {
        "message": "Action approved",
        "approval_id": str(approval.id),
        "status": approval.status,
        "decided_at": approval.decided_at
    }


@router.post("/{approval_id}/reject")
async def reject_action(approval_id: UUID, request: RejectRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = ApprovalService(db)
    approval = service.reject(approval_id, current_user.id, request.notes)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    logger.info("Rejected tool execution %s by user %s", approval_id, current_user.id)
    return {
        "message": "Action rejected",
        "approval_id": str(approval.id),
        "status": approval.status,
        "decided_at": approval.decided_at
    }


@router.get("/{approval_id}")
async def get_approval(approval_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = ApprovalService(db)
    approval = service.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    return {
        "id": str(approval.id),
        "agent_id": str(approval.agent_id),
        "action": approval.action,
        "parameters": approval.parameters,
        "reason": approval.reason,
        "risk_level": approval.risk_level,
        "status": approval.status,
        "requested_at": approval.requested_at,
        "decided_at": approval.decided_at,
        "decided_by": str(approval.decided_by) if approval.decided_by else None,
        "decision_notes": approval.decision_notes,
        "created_at": str(approval.created_at)
    }
