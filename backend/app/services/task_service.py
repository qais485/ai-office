import asyncio
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone

from app.models.task import Task, TaskStatus, TaskPriority, TaskType
from app.schemas.task import TaskCreate, TaskUpdate

logger = logging.getLogger(__name__)


class TaskService:
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

    def _publish_task_event(self, event_type, task: Task, old_status: str = "") -> None:
        try:
            from app.events.publisher import publish_task_event
            from app.events.types import EventType
            self._fire_async(
                publish_task_event(
                    event_type=event_type,
                    task_id=task.id,
                    agent_id=task.agent_id,
                    title=task.title,
                    status=task.status.value if hasattr(task.status, 'value') else str(task.status),
                    old_status=old_status,
                    priority=task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
                )
            )
        except Exception as e:
            logger.warning("Failed to publish task event", exc_info=True)

    def get_tasks(self, agent_id: Optional[UUID] = None, status: Optional[str] = None,
                  priority: Optional[str] = None, task_type: Optional[str] = None,
                  limit: int = 100) -> List[Task]:
        query = self.db.query(Task)
        if agent_id:
            query = query.filter(Task.agent_id == agent_id)
        if status:
            query = query.filter(Task.status == status)
        if priority:
            query = query.filter(Task.priority == priority)
        if task_type:
            query = query.filter(Task.task_type == task_type)
        return query.order_by(Task.created_at.desc()).limit(limit).all()

    def get_task(self, task_id: UUID) -> Optional[Task]:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def create_task(self, task_data: TaskCreate) -> Task:
        task = Task(**task_data.model_dump())
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        from app.events.types import EventType
        self._publish_task_event(EventType.TASK_CREATED, task)
        return task

    def update_task(self, task_id: UUID, task_data: TaskUpdate) -> Optional[Task]:
        task = self.get_task(task_id)
        if task:
            old_status = task.status.value if hasattr(task.status, 'value') else str(task.status)
            update_data = task_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(task, key, value)
            self.db.commit()
            self.db.refresh(task)
            from app.events.types import EventType
            self._publish_task_event(EventType.TASK_UPDATED, task, old_status)
        return task

    def delete_task(self, task_id: UUID) -> bool:
        task = self.get_task(task_id)
        if task:
            self.db.delete(task)
            self.db.commit()
            return True
        return False

    def start_task(self, task_id: UUID) -> Optional[Task]:
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now(timezone.utc).isoformat()
            self.db.commit()
            self.db.refresh(task)
        return task

    def complete_task(self, task_id: UUID, result: str = None, output_json: dict = None) -> Optional[Task]:
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.RUNNING:
            old_status = task.status.value
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.output_json = output_json
            task.completed_at = datetime.now(timezone.utc).isoformat()
            self.db.commit()
            self.db.refresh(task)
            from app.events.types import EventType
            self._publish_task_event(EventType.TASK_COMPLETED, task, old_status)
        return task

    def fail_task(self, task_id: UUID, error_message: str) -> Optional[Task]:
        task = self.get_task(task_id)
        if task and task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            old_status = task.status.value
            task.status = TaskStatus.FAILED
            task.error_message = error_message
            task.completed_at = datetime.now(timezone.utc).isoformat()
            self.db.commit()
            self.db.refresh(task)
            from app.events.types import EventType
            self._publish_task_event(EventType.TASK_FAILED, task, old_status)
        return task

    def cancel_task(self, task_id: UUID) -> Optional[Task]:
        task = self.get_task(task_id)
        if task and task.status in [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL]:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc).isoformat()
            self.db.commit()
            self.db.refresh(task)
        return task

    def wait_for_approval(self, task_id: UUID, approval_id: UUID) -> Optional[Task]:
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.WAITING_APPROVAL
            task.approval_id = approval_id
            self.db.commit()
            self.db.refresh(task)
        return task

    def handoff_task(self, task_id: UUID, to_agent_id: UUID) -> Optional[Task]:
        task = self.get_task(task_id)
        if task and task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task.assigned_to_agent_id = to_agent_id
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.completed_at = None
            self.db.commit()
            self.db.refresh(task)
        return task

    def get_subtasks(self, parent_task_id: UUID) -> List[Task]:
        return self.db.query(Task).filter(Task.parent_task_id == parent_task_id).order_by(Task.created_at.desc()).all()

    def get_task_stats(self, agent_id: Optional[UUID] = None, user_id: Optional[UUID] = None) -> dict:
        from sqlalchemy import func
        from app.models.agent import AIAgent

        # Strict per-account scoping: only tasks of the requesting account's
        # agents are counted (optionally narrowed to one owned agent).
        query = self.db.query(Task).join(AIAgent, Task.agent_id == AIAgent.id)
        if user_id is not None:
            query = query.filter(AIAgent.user_id == user_id)
        if agent_id:
            query = query.filter(Task.agent_id == agent_id)

        total = query.count()
        pending = query.filter(Task.status == TaskStatus.PENDING).count()
        running = query.filter(Task.status == TaskStatus.RUNNING).count()
        completed = query.filter(Task.status == TaskStatus.COMPLETED).count()
        failed = query.filter(Task.status == TaskStatus.FAILED).count()
        cancelled = query.filter(Task.status == TaskStatus.CANCELLED).count()
        waiting = query.filter(Task.status == TaskStatus.WAITING_APPROVAL).count()

        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "waiting_approval": waiting
        }

    def create_agent_task(self, from_agent_id: UUID, to_agent_id: UUID, title: str,
                          description: str = None, priority: str = "medium",
                          input_json: dict = None, task_type: str = "general") -> Task:
        task = Task(
            title=title,
            description=description,
            agent_id=to_agent_id,
            assigned_by=None,
            assigned_to_agent_id=to_agent_id,
            priority=priority,
            task_type=task_type,
            input_json=input_json,
            status=TaskStatus.PENDING
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task
