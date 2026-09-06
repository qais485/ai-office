import asyncio
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timedelta, timezone

from app.models.approval import Approval
from app.models.approval_event import ApprovalEvent
from app.schemas.approval import ApprovalCreate
from app.api.websocket import manager

logger = logging.getLogger(__name__)


class ApprovalService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _fire_async(coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            asyncio.run(coro)

    def _publish_approval_event(self, event_type, approval: Approval, old_status: str = "") -> None:
        try:
            from app.events.publisher import publish_approval_event
            self._fire_async(
                publish_approval_event(
                    event_type=event_type,
                    approval_id=approval.id,
                    agent_id=approval.agent_id,
                    action=approval.action,
                    risk_level=approval.risk_level,
                    status=approval.status,
                    old_status=old_status,
                )
            )
        except Exception as e:
            logger.warning("Failed to publish approval event", exc_info=True)

    def get_approvals(self, status: Optional[str] = None, agent_id: Optional[UUID] = None, user_id: Optional[UUID] = None, role: Optional[str] = None) -> List[Approval]:
        query = self.db.query(Approval)
        if status:
            query = query.filter(Approval.status == status)
        if agent_id:
            query = query.filter(Approval.agent_id == agent_id)
        if user_id is not None and role not in ("ceo", "admin"):
            from app.models.agent import AIAgent
            user_agent_ids = [a.id for a in self.db.query(AIAgent.id).filter(AIAgent.user_id == user_id).all()]
            if not user_agent_ids:
                return []
            query = query.filter(Approval.agent_id.in_(user_agent_ids))
        return query.order_by(Approval.created_at.desc()).all()

    def get_approval(self, approval_id: UUID) -> Optional[Approval]:
        return self.db.query(Approval).filter(Approval.id == approval_id).first()

    def get_approval_with_agent(self, approval_id: UUID, user_id: Optional[UUID] = None, role: Optional[str] = None) -> Optional[dict]:
        from app.models.agent import AIAgent
        from app.models.user import User
        
        approval = self.get_approval(approval_id)
        if not approval:
            return None
        
        # Verify user owns the agent if not CEO/Admin
        if user_id is not None and role not in ("ceo", "admin"):
            agent = self.db.query(AIAgent).filter(AIAgent.id == approval.agent_id).first()
            if not agent or agent.user_id != user_id:
                return None
        
        agent = self.db.query(AIAgent).filter(AIAgent.id == approval.agent_id).first()
        decided_by_user = None
        if approval.decided_by:
            decided_by_user = self.db.query(User).filter(User.id == approval.decided_by).first()
        
        return {
            "id": str(approval.id),
            "agent_id": str(approval.agent_id),
            "agent_name": agent.name if agent else "Unknown Agent",
            "agent_role": agent.role if agent else "Unknown",
            "task_id": str(approval.task_id) if approval.task_id else None,
            "action": approval.action,
            "tool_id": str(approval.tool_id) if approval.tool_id else None,
            "target": approval.target,
            "parameters": approval.parameters,
            "reason": approval.reason,
            "risk_level": approval.risk_level,
            "status": approval.status,
            "requested_at": approval.requested_at,
            "decided_at": approval.decided_at,
            "decided_by": str(approval.decided_by) if approval.decided_by else None,
            "decided_by_name": decided_by_user.name if decided_by_user else None,
            "decision_notes": approval.decision_notes,
            "expires_at": approval.expires_at,
            "retry_count": approval.retry_count,
            "max_retries": approval.max_retries,
            "created_at": approval.created_at.isoformat() if approval.created_at else None,
            "updated_at": approval.updated_at.isoformat() if approval.updated_at else None
        }

    def get_approvals_with_agents(self, status: Optional[str] = None, agent_id: Optional[UUID] = None, risk_level: Optional[str] = None, user_id: Optional[UUID] = None, role: Optional[str] = None) -> List[dict]:
        from app.models.agent import AIAgent
        
        approvals = self.get_approvals(status=status, agent_id=agent_id, user_id=user_id, role=role)
        
        if risk_level:
            approvals = [a for a in approvals if a.risk_level == risk_level]
        
        agent_ids = list(set(a.agent_id for a in approvals))
        agents = self.db.query(AIAgent).filter(AIAgent.id.in_(agent_ids)).all() if agent_ids else []
        agent_map = {str(a.id): a for a in agents}
        
        result = []
        for approval in approvals:
            agent = agent_map.get(str(approval.agent_id))
            result.append({
                "id": str(approval.id),
                "agent_id": str(approval.agent_id),
                "agent_name": agent.name if agent else "Unknown Agent",
                "agent_role": agent.role if agent else "Unknown",
                "action": approval.action,
                "parameters": approval.parameters,
                "reason": approval.reason,
                "risk_level": approval.risk_level,
                "status": approval.status,
                "requested_at": approval.requested_at,
                "decided_at": approval.decided_at,
                "decision_notes": approval.decision_notes,
                "created_at": approval.created_at.isoformat() if approval.created_at else None
            })
        
        return result

    def _create_event(self, approval_id: UUID, agent_id: UUID, event_type: str, old_status: str, new_status: str, description: str, performed_by: Optional[UUID] = None):
        event = ApprovalEvent(
            approval_id=approval_id,
            agent_id=agent_id,
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            description=description,
            performed_by=performed_by
        )
        self.db.add(event)

    def create_approval(self, data: ApprovalCreate, expires_in_hours: Optional[int] = None) -> Approval:
        from app.models.agent import AIAgent
        from app.models.room import OfficeRoom
        
        expires_at = None
        if expires_in_hours:
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)).isoformat()
        
        approval = Approval(
            **data.model_dump(),
            status="pending",
            requested_at=datetime.now(timezone.utc).isoformat(),
            expires_at=expires_at
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        
        self._create_event(
            approval.id,
            data.agent_id,
            "created",
            None,
            "pending",
            f"Approval requested: {data.action}"
        )
        self.db.commit()

        from app.events.types import EventType
        self._publish_approval_event(EventType.APPROVAL_CREATED, approval)

        agent = self.db.query(AIAgent).filter(AIAgent.id == data.agent_id).first()
        if agent:
            room = self.db.query(OfficeRoom).filter(OfficeRoom.current_agent_id == agent.id).first()
            if room:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(
                            manager.broadcast_approval_request(
                                approval.id,
                                agent.id,
                                str(room.id),
                                data.reason or "Approval Request"
                            )
                        )
                except Exception:
                    logger.warning("Failed to broadcast approval request", exc_info=True)
        
        return approval

    def approve(self, approval_id: UUID, decided_by: UUID, notes: Optional[str] = None) -> Optional[Approval]:
        approval = self.get_approval(approval_id)
        if approval and approval.status == "pending":
            old_status = approval.status
            approval.status = "approved"
            approval.decided_at = datetime.now(timezone.utc).isoformat()
            approval.decided_by = decided_by
            approval.decision_notes = notes

            self._create_event(
                approval.id, approval.agent_id, "approved", old_status, "approved",
                f"Approved: {notes or 'No notes'}", decided_by,
            )
            self.db.commit()
            self.db.refresh(approval)

            from app.events.types import EventType
            self._publish_approval_event(EventType.APPROVAL_APPROVED, approval, old_status)

            # Trigger execution of the approved action
            try:
                from app.services.tool_execution_service import ToolExecutionService
                exec_service = ToolExecutionService(self.db)
                exec_result = exec_service.execute_approved_action(approval_id)
                approval.parameters = {
                    **(approval.parameters or {}),
                    "_execution_result": exec_result,
                }
                self.db.commit()
            except Exception:
                logger.warning("Failed to execute approved action", exc_info=True)

        return approval

    def reject(self, approval_id: UUID, decided_by: UUID, notes: Optional[str] = None) -> Optional[Approval]:
        approval = self.get_approval(approval_id)
        if approval and approval.status == "pending":
            old_status = approval.status
            approval.status = "rejected"
            approval.decided_at = datetime.now(timezone.utc).isoformat()
            approval.decided_by = decided_by
            approval.decision_notes = notes
            
            self._create_event(
                approval.id,
                approval.agent_id,
                "rejected",
                old_status,
                "rejected",
                f"Rejected: {notes or 'No notes'}",
                decided_by
            )
            self.db.commit()
            self.db.refresh(approval)

            from app.events.types import EventType
            self._publish_approval_event(EventType.APPROVAL_REJECTED, approval, old_status)
        return approval

    def cancel(self, approval_id: UUID) -> Optional[Approval]:
        approval = self.get_approval(approval_id)
        if approval and approval.status == "pending":
            old_status = approval.status
            approval.status = "cancelled"
            
            self._create_event(
                approval.id,
                approval.agent_id,
                "cancelled",
                old_status,
                "cancelled",
                "Approval cancelled"
            )
            self.db.commit()
            self.db.refresh(approval)
        return approval

    def expire(self, approval_id: UUID) -> Optional[Approval]:
        approval = self.get_approval(approval_id)
        if approval and approval.status == "pending":
            old_status = approval.status
            approval.status = "expired"
            approval.decided_at = datetime.now(timezone.utc).isoformat()
            approval.decision_notes = "Approval expired"
            
            self._create_event(
                approval.id,
                approval.agent_id,
                "expired",
                old_status,
                "expired",
                "Approval expired automatically"
            )
            self.db.commit()
            self.db.refresh(approval)
        return approval

    def retry(self, approval_id: UUID) -> Optional[Approval]:
        approval = self.get_approval(approval_id)
        if approval and approval.status in ["rejected", "expired"]:
            if approval.retry_count < approval.max_retries:
                old_status = approval.status
                approval.status = "pending"
                approval.retry_count += 1
                approval.requested_at = datetime.now(timezone.utc).isoformat()
                approval.decided_at = None
                approval.decided_by = None
                approval.decision_notes = None
                
                self._create_event(
                    approval.id,
                    approval.agent_id,
                    "retried",
                    old_status,
                    "pending",
                    f"Approval retried (attempt {approval.retry_count})"
                )
                self.db.commit()
                self.db.refresh(approval)
        return approval

    def expire_pending_approvals(self) -> int:
        now = datetime.now(timezone.utc)
        expired = self.db.query(Approval).filter(
            Approval.status == "pending",
            Approval.expires_at.isnot(None),
            Approval.expires_at < now.isoformat()
        ).all()
        
        count = 0
        for approval in expired:
            old_status = approval.status
            approval.status = "expired"
            approval.decided_at = now.isoformat()
            approval.decision_notes = "Approval expired automatically"
            
            self._create_event(
                approval.id,
                approval.agent_id,
                "expired",
                old_status,
                "expired",
                "Approval expired automatically"
            )
            count += 1
        
        self.db.commit()
        return count

    def get_pending_count(self) -> int:
        return self.db.query(Approval).filter(Approval.status == "pending").count()

    def get_stats(self, user_id: Optional[UUID] = None, role: Optional[str] = None) -> dict:
        from app.models.agent import AIAgent
        if user_id is not None and role not in ("ceo", "admin"):
            user_agent_ids = [a.id for a in self.db.query(AIAgent.id).filter(AIAgent.user_id == user_id).all()]
            if not user_agent_ids:
                return {"pending": 0, "approved": 0, "rejected": 0, "expired": 0, "cancelled": 0, "total": 0}
            base_filter = Approval.agent_id.in_(user_agent_ids)
        else:
            base_filter = None

        def _count(extra_filter=None):
            q = self.db.query(Approval).filter(Approval.status == "pending")
            if base_filter is not None:
                q = q.filter(base_filter)
            if extra_filter is not None:
                q = q.filter(extra_filter)
            return q.count()

        pending = _count()
        approved = _count(Approval.status == "approved")
        rejected = _count(Approval.status == "rejected")
        expired = _count(Approval.status == "expired")
        cancelled = _count(Approval.status == "cancelled")
        
        return {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "expired": expired,
            "cancelled": cancelled,
            "total": pending + approved + rejected + expired + cancelled
        }

    def get_events(self, approval_id: UUID) -> List[ApprovalEvent]:
        return self.db.query(ApprovalEvent).filter(
            ApprovalEvent.approval_id == approval_id
        ).order_by(ApprovalEvent.created_at.desc()).all()
