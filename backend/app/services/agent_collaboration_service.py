from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

from app.models.agent import AIAgent, LifecycleStatus
from app.models.task import Task, TaskStatus, TaskPriority
from app.services.task_service import TaskService
from app.services.activity_service import ActivityService
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationCreate
import logging

logger = logging.getLogger(__name__)


class AgentCollaborationService:
    def __init__(self, db: Session):
        self.db = db

    def create_collaboration_task(
        self,
        from_agent_id: UUID,
        to_agent_id: UUID,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium",
        input_json: Optional[dict] = None
    ) -> Dict[str, Any]:
        from_agent = self.db.query(AIAgent).filter(AIAgent.id == from_agent_id).first()
        to_agent = self.db.query(AIAgent).filter(AIAgent.id == to_agent_id).first()
        
        if not from_agent:
            return {"success": False, "error": "Source agent not found"}
        if not to_agent:
            return {"success": False, "error": "Target agent not found"}
        
        if from_agent.lifecycle_status != LifecycleStatus.ACTIVE:
            return {"success": False, "error": "Source agent is not active"}
        if to_agent.lifecycle_status != LifecycleStatus.ACTIVE:
            return {"success": False, "error": "Target agent is not active"}
        
        logger.info("Creating collaboration task: %s -> %s: %s", from_agent_id, to_agent_id, title)
        task_service = TaskService(self.db)
        task = task_service.create_agent_task(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            title=title,
            description=description,
            priority=priority,
            input_json=input_json
        )
        
        activity_service = ActivityService(self.db)
        activity_service.log_agent_action(
            agent_id=from_agent_id,
            activity_type="collaboration",
            description=f"Created task for {to_agent.name}: {title}",
            task_id=task.id
        )
        
        notification_service = NotificationService(self.db)
        from app.models.user import User, UserRole
        ceo = self.db.query(User).filter(User.role == UserRole.CEO).first()
        if ceo:
            notification_service.create_notification(
                NotificationCreate(
                    user_id=ceo.id,
                    type="agent_collaboration",
                    title=f"Agent Collaboration: {from_agent.name} → {to_agent.name}",
                    message=f"{from_agent.name} assigned task to {to_agent.name}: {title}",
                    reference_type="task",
                    reference_id=task.id
                )
            )
        
        return {
            "success": True,
            "task_id": str(task.id),
            "from_agent": from_agent.name,
            "to_agent": to_agent.name,
            "title": title
        }

    def get_agent_collaborations(self, agent_id: UUID) -> Dict[str, Any]:
        assigned_tasks = self.db.query(Task).filter(
            Task.assigned_to_agent_id == agent_id
        ).order_by(Task.created_at.desc()).all()
        
        created_tasks = self.db.query(Task).filter(
            Task.agent_id == agent_id,
            Task.assigned_to_agent_id.isnot(None),
            Task.assigned_to_agent_id != agent_id
        ).order_by(Task.created_at.desc()).all()
        
        return {
            "assigned_to_me": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status.value if t.status else None,
                    "from_agent_id": str(t.agent_id) if t.agent_id else None,
                    "created_at": str(t.created_at)
                }
                for t in assigned_tasks
            ],
            "created_by_me": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status.value if t.status else None,
                    "assigned_to": str(t.assigned_to_agent_id) if t.assigned_to_agent_id else None,
                    "created_at": str(t.created_at)
                }
                for t in created_tasks
            ]
        }

    def get_collaboration_stats(self) -> Dict[str, Any]:
        from sqlalchemy import func
        
        total_collaborations = self.db.query(Task).filter(
            Task.assigned_to_agent_id.isnot(None)
        ).count()
        
        active_collaborations = self.db.query(Task).filter(
            Task.assigned_to_agent_id.isnot(None),
            Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        ).count()
        
        completed_collaborations = self.db.query(Task).filter(
            Task.assigned_to_agent_id.isnot(None),
            Task.status == TaskStatus.COMPLETED
        ).count()
        
        agents = self.db.query(AIAgent).all()
        agent_stats = []
        
        for agent in agents:
            assigned = self.db.query(Task).filter(Task.assigned_to_agent_id == agent.id).count()
            created = self.db.query(Task).filter(
                Task.agent_id == agent.id,
                Task.assigned_to_agent_id.isnot(None)
            ).count()
            
            agent_stats.append({
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "tasks_assigned": assigned,
                "tasks_created": created
            })
        
        return {
            "total": total_collaborations,
            "active": active_collaborations,
            "completed": completed_collaborations,
            "by_agent": sorted(agent_stats, key=lambda x: x["tasks_assigned"], reverse=True)
        }

    def can_agents_collaborate(self, from_agent_id: UUID, to_agent_id: UUID) -> Dict[str, Any]:
        from_agent = self.db.query(AIAgent).filter(AIAgent.id == from_agent_id).first()
        to_agent = self.db.query(AIAgent).filter(AIAgent.id == to_agent_id).first()
        
        if not from_agent:
            return {"can_collaborate": False, "reason": "Source agent not found"}
        if not to_agent:
            return {"can_collaborate": False, "reason": "Target agent not found"}
        
        if from_agent.lifecycle_status != LifecycleStatus.ACTIVE:
            return {"can_collaborate": False, "reason": "Source agent is not active"}
        if to_agent.lifecycle_status != LifecycleStatus.ACTIVE:
            return {"can_collaborate": False, "reason": "Target agent is not active"}
        
        return {
            "can_collaborate": True,
            "from_agent": from_agent.name,
            "to_agent": to_agent.name
        }

    def get_available_collaboration_partners(self, agent_id: UUID) -> List[Dict[str, Any]]:
        agents = self.db.query(AIAgent).filter(
            AIAgent.id != agent_id,
            AIAgent.lifecycle_status == LifecycleStatus.ACTIVE
        ).all()
        
        return [
            {
                "id": str(agent.id),
                "name": agent.name,
                "role": agent.role,
                "status": agent.status
            }
            for agent in agents
        ]
