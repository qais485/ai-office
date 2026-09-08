from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.room import OfficeRoom, RoomStatus
from app.models.task import Task, TaskStatus
from app.models.approval import Approval
from app.models.activity import AgentActivity
from app.models.email import EmailMessage
from app.schemas.dashboard import DashboardSummary, AgentSummary, TaskSummary
import logging

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def _filter_user_agents(self, query, user_id: Optional[UUID] = None):
        """Strict per-account scoping — every dashboard view shows only the
        agents owned by the requesting account. No role bypasses this."""
        if user_id is not None:
            query = query.filter(AIAgent.user_id == user_id)
        return query

    def _filter_user_rooms(self, query, user_id: Optional[UUID] = None):
        if user_id is not None:
            query = query.filter(OfficeRoom.user_id == user_id)
        return query

    def get_summary(self, user_id: Optional[UUID] = None) -> DashboardSummary:
        logger.debug("Fetching dashboard summary for user %s", user_id)

        # ── Batched counts: 3 grouped queries instead of ~13 COUNT round-trips.
        # With a remote DB (Neon) every round-trip costs 100s of ms, so the
        # sequential COUNT queries made this endpoint take 10-20+s.
        agent_counts = dict(
            self._filter_user_agents(self.db.query(AIAgent.status, func.count(AIAgent.id)), user_id)
            .group_by(AIAgent.status)
            .all()
        )
        total_agents = sum(agent_counts.values())
        active_agents = agent_counts.get(AgentStatus.ACTIVE, 0)
        busy_agents = agent_counts.get(AgentStatus.BUSY, 0)
        inactive_agents = agent_counts.get(AgentStatus.INACTIVE, 0)

        room_counts = dict(
            self._filter_user_rooms(self.db.query(OfficeRoom.status, func.count(OfficeRoom.id)), user_id)
            .group_by(OfficeRoom.status)
            .all()
        )
        total_rooms = sum(room_counts.values())
        available_rooms = room_counts.get(RoomStatus.AVAILABLE, 0)
        occupied_rooms = room_counts.get(RoomStatus.OCCUPIED, 0)
        maintenance_rooms = room_counts.get(RoomStatus.MAINTENANCE, 0)

        task_query = self._user_task_query().with_entities(Task.status, func.count(Task.id))
        if user_id is not None:
            task_query = task_query.filter(AIAgent.user_id == user_id)
        task_counts = dict(
            task_query
            .group_by(Task.status)
            .all()
        )
        total_tasks = sum(task_counts.values())
        pending_tasks = task_counts.get(TaskStatus.PENDING, 0)
        in_progress_tasks = task_counts.get(TaskStatus.RUNNING, 0)
        completed_tasks = task_counts.get(TaskStatus.COMPLETED, 0)
        failed_tasks = task_counts.get(TaskStatus.FAILED, 0)

        agent_list_query = self.db.query(AIAgent)
        agent_list_query = self._filter_user_agents(agent_list_query, user_id)
        agents = agent_list_query.all()
        agent_summaries = []
        room_ids = {a.room_id for a in agents if a.room_id}
        room_names: dict = {}
        if room_ids:
            rooms = self.db.query(OfficeRoom).filter(OfficeRoom.id.in_(room_ids)).all()
            room_names = {r.id: r.name for r in rooms}
        for agent in agents:
            agent_summaries.append(AgentSummary(
                id=agent.id,
                name=agent.name,
                role=agent.role,
                status=agent.status.value if hasattr(agent.status, 'value') else agent.status,
                room_name=room_names.get(agent.room_id),
            ))

        recent_tasks_query = (
            self.db.query(Task, AIAgent.name)
            .join(AIAgent, Task.agent_id == AIAgent.id)
            .filter(AIAgent.user_id == user_id)
            .order_by(Task.created_at.desc())
            .limit(10)
            .all()
        ) if user_id is not None else []
        recent_tasks = [
            TaskSummary(
                id=task.id,
                title=task.title,
                status=task.status.value if hasattr(task.status, 'value') else task.status,
                priority=task.priority.value if hasattr(task.priority, 'value') else task.priority,
                agent_name=agent_name,
                created_at=task.created_at.isoformat() if task.created_at else "",
            )
            for task, agent_name in recent_tasks_query
        ]

        pending_actions_query = (
            self.db.query(Task, AIAgent.name)
            .join(AIAgent, Task.agent_id == AIAgent.id)
            .filter(
                AIAgent.user_id == user_id,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]),
            )
            .order_by(Task.created_at.desc())
            .limit(10)
            .all()
        ) if user_id is not None else []
        pending_actions = [
            TaskSummary(
                id=task.id,
                title=task.title,
                status=task.status.value if hasattr(task.status, 'value') else task.status,
                priority=task.priority.value if hasattr(task.priority, 'value') else task.priority,
                agent_name=agent_name,
                created_at=task.created_at.isoformat() if task.created_at else "",
            )
            for task, agent_name in pending_actions_query
        ]

        return DashboardSummary(
            total_agents=total_agents,
            active_agents=active_agents,
            busy_agents=busy_agents,
            inactive_agents=inactive_agents,
            total_rooms=total_rooms,
            available_rooms=available_rooms,
            occupied_rooms=occupied_rooms,
            maintenance_rooms=maintenance_rooms,
            total_tasks=total_tasks,
            pending_tasks=pending_tasks,
            in_progress_tasks=in_progress_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            agents=agent_summaries,
            recent_tasks=recent_tasks,
            pending_actions=pending_actions,
        )

    def _user_task_query(self):
        """Task counts scoped through the owning agent — tasks belong to an
        agent, agents belong to an account."""
        return self.db.query(Task).join(AIAgent, Task.agent_id == AIAgent.id)

    def get_ceo_summary(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        logger.debug("Fetching CEO summary for user %s", user_id)

        agent_query = self.db.query(func.count(AIAgent.id))
        agent_query = self._filter_user_agents(agent_query, user_id)
        total_agents = agent_query.scalar() or 0

        agent_active_query = self.db.query(func.count(AIAgent.id)).filter(
            AIAgent.status.in_([AgentStatus.ACTIVE, AgentStatus.BUSY])
        )
        agent_active_query = self._filter_user_agents(agent_active_query, user_id)
        active_agents = agent_active_query.scalar() or 0

        agent_inactive_query = self.db.query(func.count(AIAgent.id)).filter(
            AIAgent.status == AgentStatus.INACTIVE
        )
        agent_inactive_query = self._filter_user_agents(agent_inactive_query, user_id)
        inactive_agents = agent_inactive_query.scalar() or 0

        agent_error_query = self.db.query(func.count(AIAgent.id)).filter(
            AIAgent.lifecycle_status == LifecycleStatus.ERROR
        )
        agent_error_query = self._filter_user_agents(agent_error_query, user_id)
        error_agents = agent_error_query.scalar() or 0

        def _owned_task_count(extra_filter=None):
            q = self._user_task_query()
            if user_id is not None:
                q = q.filter(AIAgent.user_id == user_id)
            if extra_filter is not None:
                q = q.filter(extra_filter)
            return q.with_entities(func.count(Task.id)).scalar() or 0

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        total_tasks = _owned_task_count()
        tasks_today = _owned_task_count(Task.created_at >= today_start)
        tasks_completed = _owned_task_count(Task.status == TaskStatus.COMPLETED)
        tasks_running = _owned_task_count(Task.status == TaskStatus.RUNNING)
        tasks_failed = _owned_task_count(Task.status == TaskStatus.FAILED)

        success_rate = round((tasks_completed / total_tasks * 100), 1) if total_tasks > 0 else 0

        def _owned_approval_count(status_value):
            q = (
                self.db.query(func.count(Approval.id))
                .join(AIAgent, Approval.agent_id == AIAgent.id)
            )
            if user_id is not None:
                q = q.filter(AIAgent.user_id == user_id)
            return q.filter(Approval.status == status_value).scalar() or 0

        pending_approvals = _owned_approval_count("pending")

        def _owned_email_count(created_after):
            q = (
                self.db.query(func.count(EmailMessage.id))
                .join(AIAgent, EmailMessage.agent_id == AIAgent.id)
            )
            if user_id is not None:
                q = q.filter(AIAgent.user_id == user_id)
            return q.filter(EmailMessage.created_at >= created_after).scalar() or 0

        emails_today = _owned_email_count(today_start)

        room_query = self.db.query(func.count(OfficeRoom.id))
        room_query = self._filter_user_rooms(room_query, user_id)
        room_total = room_query.scalar() or 0

        return {
            "agents": {
                "total": total_agents,
                "active": active_agents,
                "inactive": inactive_agents,
                "error": error_agents,
            },
            "tasks": {
                "total": total_tasks,
                "today": tasks_today,
                "completed": tasks_completed,
                "running": tasks_running,
                "failed": tasks_failed,
                "success_rate": success_rate,
            },
            "approvals": {
                "pending": pending_approvals,
            },
            "emails": {
                "today": emails_today,
            },
            "rooms": {
                "total": room_total,
            },
        }

    def get_agent_status_overview(self, user_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        agent_query = self.db.query(AIAgent)
        agent_query = self._filter_user_agents(agent_query, user_id)
        agents = agent_query.all()

        if not agents:
            return []

        # ── Batched per-agent task stats: 2 grouped queries instead of
        # (3 counts + 1 current task + 1 room) per agent.
        agent_ids = [a.id for a in agents]
        status_counts: dict = {}
        for agent_id, status, cnt in (
            self.db.query(Task.agent_id, Task.status, func.count(Task.id))
            .filter(Task.agent_id.in_(agent_ids))
            .group_by(Task.agent_id, Task.status)
            .all()
        ):
            status_counts.setdefault(agent_id, {})[status] = cnt

        current_tasks: dict = {}
        for t in (
            self.db.query(Task)
            .filter(
                Task.agent_id.in_(agent_ids),
                Task.status.in_([TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL]),
            )
            .order_by(Task.created_at.desc())
            .all()
        ):
            current_tasks.setdefault(t.agent_id, t)  # keep newest per agent

        room_ids = {a.room_id for a in agents if a.room_id}
        rooms_by_id: dict = {}
        if room_ids:
            for r in self.db.query(OfficeRoom).filter(OfficeRoom.id.in_(room_ids)).all():
                rooms_by_id[r.id] = r

        overview = []
        for agent in agents:
            counts = status_counts.get(agent.id, {})
            current_task = current_tasks.get(agent.id)
            room = rooms_by_id.get(agent.room_id) if agent.room_id else None

            overview.append({
                "id": str(agent.id),
                "name": agent.name,
                "role": agent.role,
                "status": agent.status.value if hasattr(agent.status, 'value') else agent.status,
                "lifecycle_status": agent.lifecycle_status.value if agent.lifecycle_status else None,
                "room": {
                    "id": str(room.id),
                    "name": room.name,
                } if room else None,
                "current_task": {
                    "id": str(current_task.id),
                    "title": current_task.title,
                    "status": current_task.status.value if hasattr(current_task.status, 'value') else current_task.status,
                } if current_task else None,
                "tasks": {
                    "pending": counts.get(TaskStatus.PENDING, 0),
                    "completed": counts.get(TaskStatus.COMPLETED, 0),
                    "failed": counts.get(TaskStatus.FAILED, 0),
                },
                "last_active_at": str(agent.last_active_at) if agent.last_active_at else None,
                "last_error": agent.last_error if agent.last_error else None,
            })

        return overview

    def get_recent_activity(self, limit: int = 20, user_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        query = self.db.query(AgentActivity)
        if user_id is not None:
            agent_ids = [a.id for a in self._filter_user_agents(self.db.query(AIAgent), user_id).all()]
            if not agent_ids:
                return []
            query = query.filter(AgentActivity.agent_id.in_(agent_ids))
        activities = query.order_by(AgentActivity.created_at.desc()).limit(limit).all()

        # Batch agent names in ONE query (was 1 query per activity — N+1).
        agent_ids = {a.agent_id for a in activities if a.agent_id}
        agent_names: dict = {}
        if agent_ids:
            for agent in self.db.query(AIAgent).filter(AIAgent.id.in_(agent_ids)).all():
                agent_names[agent.id] = agent.name

        result = []
        for activity in activities:
            result.append({
                "id": str(activity.id),
                "agent_id": str(activity.agent_id),
                "agent_name": agent_names.get(activity.agent_id, "Unknown"),
                "activity_type": activity.activity_type,
                "description": activity.description,
                "tool_name": activity.tool_name,
                "status": activity.status,
                "created_at": str(activity.created_at),
            })

        return result

    def get_performance_metrics(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        def _owned_task_count(extra_filter=None):
            q = self._user_task_query()
            if user_id is not None:
                q = q.filter(AIAgent.user_id == user_id)
            if extra_filter is not None:
                q = q.filter(extra_filter)
            return q.with_entities(func.count(Task.id)).scalar() or 0

        total_tasks = _owned_task_count()
        completed_tasks = _owned_task_count(Task.status == TaskStatus.COMPLETED)
        failed_tasks = _owned_task_count(Task.status == TaskStatus.FAILED)

        success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        agent_query = self.db.query(AIAgent)
        agent_query = self._filter_user_agents(agent_query, user_id)
        agents = agent_query.all()
        agent_metrics = []

        for agent in agents:
            agent_total = self.db.query(func.count(Task.id)).filter(Task.agent_id == agent.id).scalar() or 0
            agent_completed = self.db.query(func.count(Task.id)).filter(
                Task.agent_id == agent.id, Task.status == TaskStatus.COMPLETED
            ).scalar() or 0
            agent_failed = self.db.query(func.count(Task.id)).filter(
                Task.agent_id == agent.id, Task.status == TaskStatus.FAILED
            ).scalar() or 0

            agent_success_rate = (agent_completed / agent_total * 100) if agent_total > 0 else 0

            agent_metrics.append({
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "role": agent.role,
                "total_tasks": agent_total,
                "completed": agent_completed,
                "failed": agent_failed,
                "success_rate": round(agent_success_rate, 1),
            })

        return {
            "overall": {
                "total_tasks": total_tasks,
                "completed": completed_tasks,
                "failed": failed_tasks,
                "success_rate": round(success_rate, 1),
            },
            "by_agent": sorted(agent_metrics, key=lambda x: x["total_tasks"], reverse=True),
        }
