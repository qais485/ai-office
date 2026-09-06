from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.audit_log import AuditLogResponse
from app.services.audit_service import AuditService
from app.api.deps import require_role
from app.models.user import User, UserRole

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[AuditLogResponse])
async def get_audit_logs(user_id: Optional[UUID] = None, agent_id: Optional[UUID] = None,
                         resource_type: Optional[str] = None, limit: int = 100,
                         db: Session = Depends(get_db), current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))):
    service = AuditService(db)
    logs = service.get_logs(user_id=user_id, agent_id=agent_id, resource_type=resource_type, limit=limit)
    logger.debug("Retrieved %d audit logs", len(logs))
    return logs


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(log_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))):
    service = AuditService(db)
    log = service.get_log(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    logger.debug("Retrieved audit log %s", log_id)
    return log
