import asyncio
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.agent import AIAgent
from app.schemas.agent import AgentCreate, AgentUpdate

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, db: Session):
        self.db = db

    def get_agents(self, user_id: Optional[UUID] = None) -> List[AIAgent]:
        query = self.db.query(AIAgent)
        if user_id is not None:
            query = query.filter(AIAgent.user_id == user_id)
        return query.all()

    def get_agent(self, agent_id: UUID, user_id: Optional[UUID] = None) -> Optional[AIAgent]:
        query = self.db.query(AIAgent).filter(AIAgent.id == agent_id)
        if user_id is not None:
            query = query.filter(AIAgent.user_id == user_id)
        return query.first()

    def get_agent_any(self, agent_id: UUID) -> Optional[AIAgent]:
        return self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()

    def create_agent(self, agent_data: AgentCreate, user_id: Optional[UUID] = None) -> AIAgent:
        agent = AIAgent(**agent_data.model_dump(), user_id=user_id)
        self.db.add(agent)
        self.db.flush()

        # Create AgentPermission records from pipe-delimited permissions string
        if agent.permissions:
            from app.models.permission import Permission
            from app.models.agent_permission import AgentPermission
            for perm_name in agent.permissions.split("|"):
                perm_name = perm_name.strip()
                if not perm_name:
                    continue
                permission = self.db.query(Permission).filter(Permission.name == perm_name).first()
                if not permission:
                    continue
                access_level = permission.default_status
                if permission.default_approval_required:
                    access_level = "approval_required"
                agent_perm = AgentPermission(
                    agent_id=agent.id,
                    permission_id=permission.id,
                    access_level=access_level,
                    conditions=None,
                    granted_by="creation",
                )
                self.db.add(agent_perm)

        # Create AgentToolAssignment records from pipe-delimited tools string
        if agent.tools:
            from app.models.tool import AgentTool
            from app.models.agent_tool_assignment import AgentToolAssignment
            for tool_name in agent.tools.split("|"):
                tool_name = tool_name.strip()
                if not tool_name:
                    continue
                tool = self.db.query(AgentTool).filter(AgentTool.name == tool_name).first()
                if not tool:
                    continue
                assignment = AgentToolAssignment(
                    agent_id=agent.id,
                    tool_id=tool.id,
                    tool_name=tool_name,
                    is_active=True,
                    is_enabled=True,
                )
                self.db.add(assignment)

        self.db.commit()
        self.db.refresh(agent)
        return agent

    def update_agent(self, agent_id: UUID, agent_data: AgentUpdate, user_id: Optional[UUID] = None) -> Optional[AIAgent]:
        agent = self.get_agent(agent_id, user_id=user_id)
        if agent:
            old_status = agent.status
            update_data = agent_data.model_dump(exclude_unset=True)
            # Always include room_id if it was in the request (to allow setting to None)
            if agent_data.room_id is not None or "room_id" in agent_data.model_fields_set:
                update_data["room_id"] = agent_data.room_id
            for key, value in update_data.items():
                setattr(agent, key, value)
            self.db.commit()
            self.db.refresh(agent)

            if "status" in update_data and update_data["status"] != old_status:
                self._publish_status_event(agent, old_status)
        return agent

    def delete_agent(self, agent_id: UUID, user_id: Optional[UUID] = None) -> bool:
        agent = self.get_agent(agent_id, user_id=user_id)
        if not agent:
            return False
        # Full dependent cleanup lives in HiringService.delete_agent — the
        # live FKs have no ON DELETE CASCADE, so deleting the agent row
        # directly fails on agent_triggers / tasks / approvals / etc.
        from app.services.hiring_service import HiringService

        return HiringService(self.db).delete_agent(agent.id)

    def _publish_status_event(self, agent: AIAgent, old_status: str) -> None:
        try:
            from app.events.publisher import publish_agent_status_changed
            room_id = str(agent.room_id) if agent.room_id else ""
            self._fire_async(
                publish_agent_status_changed(agent.id, room_id, agent.status, old_status)
            )
        except Exception as e:
            logger.warning("Failed to publish agent status event", exc_info=True)

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
