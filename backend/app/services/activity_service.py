from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.activity import AgentActivity
from app.schemas.activity import ActivityCreate
import logging

logger = logging.getLogger(__name__)


class ActivityService:
    def __init__(self, db: Session):
        self.db = db

    def log_activity(self, data: ActivityCreate) -> AgentActivity:
        logger.debug("Logging activity: type=%s", data.activity_type)
        activity = AgentActivity(**data.model_dump())
        self.db.add(activity)
        room_id = self._touch_agent_last_active(data.agent_id)
        self.db.commit()
        self.db.refresh(activity)
        self._publish_activity_event(activity, room_id)
        logger.info("Activity logged: id=%s", activity.id)
        return activity

    def _touch_agent_last_active(self, agent_id: UUID) -> Optional[str]:
        """Keep the agent's Last Active timestamp in sync with its latest
        logged activity. Returns the agent's room_id (for WS broadcast) or
        None. Best-effort: must never break activity logging."""
        try:
            from datetime import datetime, timezone

            from app.models.agent import AIAgent

            agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
            if agent is not None:
                agent.last_active_at = datetime.now(timezone.utc).isoformat()
                return str(agent.room_id) if agent.room_id else None
        except Exception:
            logger.debug("Could not touch last_active_at for agent %s", agent_id, exc_info=True)
        return None

    def _publish_activity_event(self, activity: AgentActivity, room_id: Optional[str]) -> None:
        """Broadcast activity_logged over the event bus (→ WebSocket) so
        dashboard tabs update in real time. Best-effort, thread-safe via
        publish_sync (safe from request threadpools and async loops)."""
        try:
            from app.events.bus import event_bus
            from app.events.types import ActivityEvent

            created_at = activity.created_at
            event_bus.publish_sync(ActivityEvent(
                activity_id=str(activity.id),
                agent_id=str(activity.agent_id),
                room_id=room_id or "",
                activity_type=activity.activity_type,
                description=activity.description or "",
                status=activity.status or "",
                created_at=created_at.isoformat() if created_at else "",
            ))
        except Exception:
            logger.debug("Could not publish activity_logged event", exc_info=True)

    def get_agent_activities(self, agent_id: UUID, limit: int = 50, 
                            activity_type: Optional[str] = None,
                            task_id: Optional[UUID] = None) -> List[AgentActivity]:
        query = self.db.query(AgentActivity).filter(AgentActivity.agent_id == agent_id)
        if activity_type:
            query = query.filter(AgentActivity.activity_type == activity_type)
        if task_id:
            query = query.filter(AgentActivity.task_id == task_id)
        return query.order_by(AgentActivity.created_at.desc()).limit(limit).all()

    def get_all_activities(self, limit: int = 100, activity_type: Optional[str] = None,
                          agent_id: Optional[UUID] = None) -> List[AgentActivity]:
        query = self.db.query(AgentActivity)
        if activity_type:
            query = query.filter(AgentActivity.activity_type == activity_type)
        if agent_id:
            query = query.filter(AgentActivity.agent_id == agent_id)
        return query.order_by(AgentActivity.created_at.desc()).limit(limit).all()

    def get_activity_stats(self, agent_id: Optional[UUID] = None) -> dict:
        from sqlalchemy import func
        
        query = self.db.query(AgentActivity)
        if agent_id:
            query = query.filter(AgentActivity.agent_id == agent_id)
        
        total = query.count()
        
        type_counts = {}
        types = self.db.query(AgentActivity.activity_type).distinct().all()
        for t in types:
            type_query = query.filter(AgentActivity.activity_type == t[0])
            type_counts[t[0]] = type_query.count()
        
        return {
            "total": total,
            "by_type": type_counts
        }

    def log_agent_action(self, agent_id: UUID, activity_type: str, description: str,
                        task_id: Optional[UUID] = None, tool_name: Optional[str] = None,
                        status: Optional[str] = None, metadata: Optional[dict] = None) -> AgentActivity:
        logger.debug("Agent action: agent=%s type=%s", agent_id, activity_type)
        data = ActivityCreate(
            agent_id=agent_id,
            activity_type=activity_type,
            description=description,
            task_id=task_id,
            tool_name=tool_name,
            status=status,
            metadata_json=metadata
        )
        return self.log_activity(data)
