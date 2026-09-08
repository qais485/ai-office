from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.audit_log import AuditLogResponse
from app.services.audit_service import AuditService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[AuditLogResponse])
async def get_audit_logs(user_id: Optional[UUID] = None, agent_id: Optional[UUID] = None,
                         resource_type: Optional[str] = None, limit: int = 100,
                         db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AuditService(db)
    # Strict per-account scoping: a user can only ever read their own logs,
    # regardless of any query parameter.
    logs = service.get_logs(user_id=current_user.id, agent_id=agent_id, resource_type=resource_type, limit=limit)
    logger.debug("Retrieved %d audit logs for user %s", len(logs), current_user.id)
    return logs


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(log_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AuditService(db)
    log = service.get_log(log_id)
    if not log or log.user_id != current_user.id:
        # Not found OR not owned — same answer either way (no existence leak).
        raise HTTPException(status_code=404, detail="Audit log not found")
    logger.debug("Retrieved audit log %s", log_id)
    return log
