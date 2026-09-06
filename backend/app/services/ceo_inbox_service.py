from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timedelta, timezone

from app.models.approval import Approval
from app.models.agent import AIAgent, LifecycleStatus
from app.models.task import Task, TaskStatus
from app.models.notification import Notification
import logging

logger = logging.getLogger(__name__)


class CEOInboxService:
    def __init__(self, db: Session):
        self.db = db

    def get_inbox_items(self, user_id: UUID, unread_only: bool = False, filter_type: Optional[str] = None, filter_priority: Optional[str] = None) -> List[Dict[str, Any]]:
        logger.debug("Fetching inbox items for user=%s filter=%s", user_id, filter_type)
        items: List[Dict[str, Any]] = []

        if filter_type is None or filter_type == "approval":
            items.extend(self._get_pending_approvals())
        if filter_type is None or filter_type == "agent_error":
            items.extend(self._get_error_agents())
        if filter_type is None or filter_type == "failed_task":
            items.extend(self._get_failed_tasks())
        if filter_type is None or filter_type == "pending_task":
            items.extend(self._get_high_priority_pending_tasks())
        if filter_type is None or filter_type == "notification":
            items.extend(self._get_notifications(user_id, unread_only))
        if filter_type is None or filter_type == "system":
            items.extend(self._get_system_alerts())

        items.sort(key=lambda x: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("priority", "low"), 3),
        ))

        if filter_priority:
            items = [i for i in items if i.get("priority") == filter_priority]

        return items

    def _get_pending_approvals(self) -> List[Dict[str, Any]]:
        from app.models.agent import AIAgent as Agent

        approvals = self.db.query(Approval).filter(
            Approval.status == "pending"
        ).order_by(Approval.created_at.desc()).limit(15).all()

        items = []
        for approval in approvals:
            agent = self.db.query(Agent).filter(Agent.id == approval.agent_id).first()

            expires_soon = False
            if approval.expires_at:
                try:
                    exp = approval.expires_at if isinstance(approval.expires_at, datetime) else datetime.fromisoformat(str(approval.expires_at))
                    expires_soon = exp - datetime.now(timezone.utc) < timedelta(hours=2)
                except (ValueError, TypeError):
                    pass

            priority = "medium"
            if approval.risk_level in ["critical"]:
                priority = "critical"
            elif approval.risk_level in ["high"]:
                priority = "high"
            elif expires_soon:
                priority = "high"

            items.append({
                "type": "approval",
                "id": str(approval.id),
                "title": f"Approval Required: {approval.action}",
                "message": f"Agent {agent.name if agent else 'Unknown'} requests approval for: {approval.action}" + (f" (expires soon)" if expires_soon else ""),
                "risk_level": approval.risk_level,
                "agent_name": agent.name if agent else "Unknown",
                "agent_id": str(approval.agent_id),
                "status": approval.status,
                "created_at": str(approval.created_at),
                "priority": priority,
                "expires_soon": expires_soon,
                "parameters": approval.parameters,
                "reason": approval.reason,
            })

        return items

    def _get_error_agents(self) -> List[Dict[str, Any]]:
        error_agents = self.db.query(AIAgent).filter(
            AIAgent.lifecycle_status == LifecycleStatus.ERROR
        ).all()

        items = []
        for agent in error_agents:
            last_error = agent.last_error or "Unknown error occurred"
            items.append({
                "type": "agent_error",
                "id": str(agent.id),
                "title": f"Agent Error: {agent.name}",
                "message": f"Agent {agent.name} has encountered an error: {last_error}",
                "agent_name": agent.name,
                "agent_id": str(agent.id),
                "status": "error",
                "created_at": str(agent.updated_at) if agent.updated_at else "",
                "priority": "high",
                "error_detail": last_error,
            })

        return items

    def _get_failed_tasks(self) -> List[Dict[str, Any]]:
        failed_tasks = self.db.query(Task).filter(
            Task.status == TaskStatus.FAILED
        ).order_by(Task.created_at.desc()).limit(10).all()

        items = []
        for task in failed_tasks:
            agent = self.db.query(AIAgent).filter(AIAgent.id == task.agent_id).first()
            items.append({
                "type": "failed_task",
                "id": str(task.id),
                "title": f"Task Failed: {task.title}",
                "message": f"Task failed: {task.error_message or 'No error message'}",
                "agent_name": agent.name if agent else "Unknown",
                "agent_id": str(task.agent_id),
                "status": "failed",
                "created_at": str(task.created_at),
                "priority": "medium",
                "error_detail": task.error_message,
            })

        return items

    def _get_high_priority_pending_tasks(self) -> List[Dict[str, Any]]:
        high_priority_tasks = self.db.query(Task).filter(
            Task.status == TaskStatus.PENDING,
            Task.priority.in_(["high", "urgent"])
        ).order_by(Task.created_at.desc()).limit(10).all()

        items = []
        for task in high_priority_tasks:
            agent = self.db.query(AIAgent).filter(AIAgent.id == task.agent_id).first()
            items.append({
                "type": "pending_task",
                "id": str(task.id),
                "title": f"High Priority Task: {task.title}",
                "message": f"Task waiting: {task.description or 'No description'}",
                "agent_name": agent.name if agent else "Unknown",
                "agent_id": str(task.agent_id),
                "status": "pending",
                "priority": task.priority,
                "created_at": str(task.created_at),
            })

        return items

    def _get_notifications(self, user_id: UUID, unread_only: bool = False) -> List[Dict[str, Any]]:
        query = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_archived == False,
        )
        if unread_only:
            query = query.filter(Notification.is_read == False)

        notifications = query.order_by(Notification.created_at.desc()).limit(20).all()

        items = []
        for notif in notifications:
            priority = notif.priority or "low"
            if priority == "low" and notif.type in ["approval_needed", "agent_error", "critical"]:
                priority = "high"
            elif priority == "low" and notif.type in ["task_failed", "warning"]:
                priority = "medium"

            items.append({
                "type": "notification",
                "id": str(notif.id),
                "title": notif.title,
                "message": notif.message,
                "notification_type": notif.type,
                "is_read": notif.is_read,
                "is_archived": notif.is_archived,
                "is_resolved": notif.is_resolved,
                "reference_type": notif.reference_type,
                "reference_id": str(notif.reference_id) if notif.reference_id else None,
                "created_at": str(notif.created_at),
                "priority": priority,
            })

        return items

    def _get_system_alerts(self) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []

        total_agents = self.db.query(AIAgent).count()
        active_agents = self.db.query(AIAgent).filter(
            AIAgent.status.in_(["active", "busy"])
        ).count()
        if total_agents > 0 and active_agents == 0 and total_agents > 2:
            alerts.append({
                "type": "system_alert",
                "id": "no-active-agents",
                "title": "No Active Agents",
                "message": "All agents are inactive or offline. The AI office is not operational.",
                "status": "warning",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "priority": "critical",
            })

        running_tasks = self.db.query(Task).filter(Task.status == TaskStatus.RUNNING).count()
        if running_tasks > 20:
            alerts.append({
                "type": "system_alert",
                "id": "task-backlog",
                "title": "High Task Backlog",
                "message": f"{running_tasks} tasks are currently running. Consider reviewing workload distribution.",
                "status": "warning",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "priority": "medium",
            })

        total_tasks = self.db.query(Task).count()
        failed_tasks = self.db.query(Task).filter(Task.status == TaskStatus.FAILED).count()
        if total_tasks > 0 and failed_tasks > 0:
            fail_rate = (failed_tasks / total_tasks) * 100
            if fail_rate > 30:
                alerts.append({
                    "type": "system_alert",
                    "id": "high-failure-rate",
                    "title": "High Task Failure Rate",
                    "message": f"Task failure rate is {fail_rate:.1f}% ({failed_tasks}/{total_tasks}). Review agent configurations.",
                    "status": "error",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "priority": "high",
                })

        pending_approvals = self.db.query(Approval).filter(Approval.status == "pending").count()
        if pending_approvals > 10:
            alerts.append({
                "type": "system_alert",
                "id": "approval-backlog",
                "title": "Approval Backlog",
                "message": f"{pending_approvals} approvals are pending. Review and process them to unblock agents.",
                "status": "warning",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "priority": "high",
            })

        return alerts

    def get_inbox_counts(self, user_id: UUID) -> Dict[str, int]:
        pending_approvals = self.db.query(Approval).filter(Approval.status == "pending").count()
        error_agents = self.db.query(AIAgent).filter(AIAgent.lifecycle_status == LifecycleStatus.ERROR).count()
        failed_tasks = self.db.query(Task).filter(Task.status == TaskStatus.FAILED).count()
        unread_notifications = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False,
            Notification.is_archived == False,
        ).count()

        system_alerts = len(self._get_system_alerts())

        return {
            "pending_approvals": pending_approvals,
            "error_agents": error_agents,
            "failed_tasks": failed_tasks,
            "unread_notifications": unread_notifications,
            "system_alerts": system_alerts,
            "total": pending_approvals + error_agents + failed_tasks + unread_notifications + system_alerts,
        }

    def mark_notification_read(self, notification_id: UUID) -> bool:
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.is_read = True
            self.db.commit()
            return True
        return False

    def mark_all_notifications_read(self, user_id: UUID) -> int:
        notifications = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False,
            Notification.is_archived == False,
        ).all()

        count = len(notifications)
        for notif in notifications:
            notif.is_read = True

        self.db.commit()
        return count

    def archive_notification(self, notification_id: UUID) -> bool:
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.is_archived = True
            notification.is_read = True
            self.db.commit()
            return True
        return False

    def resolve_notification(self, notification_id: UUID) -> bool:
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.is_resolved = True
            notification.is_read = True
            self.db.commit()
            return True
        return False

    def approve_item(self, item_id: str, item_type: str, user_id: UUID, notes: str = None) -> Dict[str, Any]:
        if item_type == "approval":
            from app.services.approval_service import ApprovalService
            approval_svc = ApprovalService(self.db)
            result = approval_svc.approve(UUID(item_id), user_id, notes)
            if result:
                return {"success": True, "message": "Approval approved"}
            return {"success": False, "message": "Approval not found or already decided"}

        return {"success": False, "message": f"Cannot approve item type: {item_type}"}

    def reject_item(self, item_id: str, item_type: str, user_id: UUID, notes: str = None) -> Dict[str, Any]:
        if item_type == "approval":
            from app.services.approval_service import ApprovalService
            approval_svc = ApprovalService(self.db)
            result = approval_svc.reject(UUID(item_id), user_id, notes)
            if result:
                return {"success": True, "message": "Approval rejected"}
            return {"success": False, "message": "Approval not found or already decided"}

        return {"success": False, "message": f"Cannot reject item type: {item_type}"}

    def dismiss_item(self, item_id: str, item_type: str, user_id: UUID) -> Dict[str, Any]:
        if item_type == "notification":
            success = self.mark_notification_read(UUID(item_id))
            return {"success": success, "message": "Notification dismissed" if success else "Not found"}

        if item_type == "failed_task":
            task = self.db.query(Task).filter(Task.id == UUID(item_id)).first()
            if task:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                self.db.commit()
                return {"success": True, "message": "Failed task dismissed"}

        return {"success": False, "message": f"Cannot dismiss item type: {item_type}"}

    def archive_item(self, item_id: str, item_type: str, user_id: UUID) -> Dict[str, Any]:
        if item_type == "notification":
            success = self.archive_notification(UUID(item_id))
            return {"success": success, "message": "Notification archived" if success else "Not found"}
        if item_type == "approval":
            success = self.mark_notification_read(UUID(item_id))
            return {"success": success, "message": "Approval archived" if success else "Not found"}
        return {"success": False, "message": f"Cannot archive item type: {item_type}"}

    def resolve_item(self, item_id: str, item_type: str, user_id: UUID) -> Dict[str, Any]:
        if item_type == "notification":
            success = self.resolve_notification(UUID(item_id))
            return {"success": success, "message": "Notification resolved" if success else "Not found"}
        if item_type == "agent_error":
            agent = self.db.query(AIAgent).filter(AIAgent.id == UUID(item_id)).first()
            if agent:
                from app.models.agent import LifecycleStatus as LS
                agent.lifecycle_status = LS.ACTIVE
                agent.last_error = None
                self.db.commit()
                return {"success": True, "message": "Agent error resolved"}
        if item_type == "failed_task":
            task = self.db.query(Task).filter(Task.id == UUID(item_id)).first()
            if task:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                self.db.commit()
                return {"success": True, "message": "Failed task resolved"}
        return {"success": False, "message": f"Cannot resolve item type: {item_type}"}

