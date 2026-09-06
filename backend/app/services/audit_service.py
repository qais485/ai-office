from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogCreate
import logging

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def get_logs(self, user_id: Optional[UUID] = None, agent_id: Optional[UUID] = None, 
                 resource_type: Optional[str] = None, limit: int = 100) -> List[AuditLog]:
        query = self.db.query(AuditLog)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if agent_id:
            query = query.filter(AuditLog.agent_id == agent_id)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()

    def get_log(self, log_id: UUID) -> Optional[AuditLog]:
        return self.db.query(AuditLog).filter(AuditLog.id == log_id).first()

    def log(self, data: AuditLogCreate) -> AuditLog:
        logger.info("Audit log: action=%s user=%s agent=%s", data.action, data.user_id, data.agent_id)
        audit_log = AuditLog(**data.model_dump())
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        return audit_log

    def log_action(self, action: str, user_id: Optional[UUID] = None, agent_id: Optional[UUID] = None,
                   resource_type: Optional[str] = None, resource_id: Optional[UUID] = None,
                   details: Optional[dict] = None, ip_address: Optional[str] = None) -> AuditLog:
        data = AuditLogCreate(
            action=action,
            user_id=user_id,
            agent_id=agent_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        return self.log(data)
