from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.models.tool_permission import ToolPermission
from app.models.agent_tool_assignment import AgentToolAssignment
from app.schemas.tool import ToolCreate, ToolUpdate, ToolActionCreate, ToolActionUpdate, ToolPermissionCreate
import logging

logger = logging.getLogger(__name__)


class ToolService:
    def __init__(self, db: Session):
        self.db = db

    def get_tools(self, active_only: bool = False, category: Optional[str] = None) -> List[AgentTool]:
        query = self.db.query(AgentTool)
        if active_only:
            query = query.filter(AgentTool.is_active == True)
        if category:
            query = query.filter(AgentTool.category == category)
        return query.all()

    def get_tool(self, tool_id: UUID) -> Optional[AgentTool]:
        return self.db.query(AgentTool).filter(AgentTool.id == tool_id).first()

    def get_tool_by_name(self, name: str) -> Optional[AgentTool]:
        return self.db.query(AgentTool).filter(AgentTool.name == name).first()

    def create_tool(self, data: ToolCreate) -> AgentTool:
        logger.info("Creating tool: %s", data.name if hasattr(data, 'name') else 'new')
        tool = AgentTool(**data.model_dump())
        self.db.add(tool)
        self.db.commit()
        self.db.refresh(tool)
        return tool

    def update_tool(self, tool_id: UUID, data: ToolUpdate) -> Optional[AgentTool]:
        tool = self.get_tool(tool_id)
        if tool:
            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(tool, key, value)
            self.db.commit()
            self.db.refresh(tool)
        return tool

    def delete_tool(self, tool_id: UUID) -> bool:
        tool = self.get_tool(tool_id)
        if tool:
            self.db.delete(tool)
            self.db.commit()
            return True
        return False

    def get_tools_by_integration(self, integration_id: UUID) -> List[AgentTool]:
        return self.db.query(AgentTool).filter(AgentTool.integration_id == integration_id).all()

    def get_tools_by_category(self, category: str) -> List[AgentTool]:
        return self.db.query(AgentTool).filter(
            AgentTool.category == category,
            AgentTool.is_active == True
        ).all()

    def get_tool_with_actions(self, tool_id: UUID) -> Optional[dict]:
        tool = self.get_tool(tool_id)
        if not tool:
            return None

        actions = self.db.query(ToolAction).filter(
            ToolAction.tool_id == tool_id,
            ToolAction.is_active == True
        ).all()

        permissions = self.db.query(ToolPermission).filter(
            ToolPermission.tool_id == tool_id
        ).all()

        return {
            "tool": tool,
            "actions": actions,
            "permissions": permissions
        }

    def get_tools_for_template(self, template_id: UUID) -> List[AgentTool]:
        from app.models.template import AgentTemplate
        template = self.db.query(AgentTemplate).filter(AgentTemplate.id == template_id).first()
        if not template or not template.default_tools:
            return []

        return self.db.query(AgentTool).filter(
            AgentTool.name.in_(template.default_tools),
            AgentTool.is_active == True
        ).all()

    def assign_tool_to_agent(self, agent_id: UUID, tool_id: UUID, config: Optional[dict] = None) -> Optional[AgentToolAssignment]:
        logger.info("Assigning tool=%s to agent=%s", tool_id, agent_id)
        existing = self.db.query(AgentToolAssignment).filter(
            AgentToolAssignment.agent_id == agent_id,
            AgentToolAssignment.tool_id == tool_id
        ).first()

        if existing:
            existing.is_enabled = True
            if config:
                existing.config = config
            self.db.commit()
            self.db.refresh(existing)
            return existing

        assignment = AgentToolAssignment(
            agent_id=agent_id,
            tool_id=tool_id,
            is_enabled=True,
            config=config
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def remove_tool_from_agent(self, agent_id: UUID, tool_id: UUID) -> bool:
        assignment = self.db.query(AgentToolAssignment).filter(
            AgentToolAssignment.agent_id == agent_id,
            AgentToolAssignment.tool_id == tool_id
        ).first()

        if not assignment:
            return False

        assignment.is_enabled = False
        self.db.commit()
        return True

    def get_agent_tools(self, agent_id: UUID) -> List[AgentTool]:
        assignments = self.db.query(AgentToolAssignment).filter(
            AgentToolAssignment.agent_id == agent_id,
            AgentToolAssignment.is_enabled == True
        ).all()

        if not assignments:
            return []

        tool_ids = [a.tool_id for a in assignments]
        return self.db.query(AgentTool).filter(
            AgentTool.id.in_(tool_ids),
            AgentTool.is_active == True
        ).all()

    def get_tool_agents(self, tool_id: UUID) -> List[dict]:
        from app.models.agent import AIAgent
        assignments = self.db.query(AgentToolAssignment).filter(
            AgentToolAssignment.tool_id == tool_id,
            AgentToolAssignment.is_enabled == True
        ).all()

        if not assignments:
            return []

        agent_ids = [a.agent_id for a in assignments]
        agents = self.db.query(AIAgent).filter(AIAgent.id.in_(agent_ids)).all()
        return [{"id": str(a.id), "name": a.name, "role": a.role} for a in agents]

    def validate_tool_access(self, agent_id: UUID, tool_name: str, action_name: Optional[str] = None) -> tuple[bool, str]:
        from app.models.agent import AIAgent
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return False, "Agent not found"

        if agent.lifecycle_status.value != "active":
            return False, f"Agent is not active (status: {agent.lifecycle_status.value})"

        tool = self.get_tool_by_name(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' not found"

        if not tool.is_active:
            return False, f"Tool '{tool_name}' is disabled"

        assignment = self.db.query(AgentToolAssignment).filter(
            AgentToolAssignment.agent_id == agent_id,
            AgentToolAssignment.tool_id == tool.id,
            AgentToolAssignment.is_enabled == True
        ).first()

        if not assignment:
            return False, f"Tool '{tool_name}' not assigned to agent"

        if action_name:
            action = self.db.query(ToolAction).filter(
                ToolAction.tool_id == tool.id,
                ToolAction.name == action_name,
                ToolAction.is_active == True
            ).first()

            if not action:
                return False, f"Action '{action_name}' not found in tool '{tool_name}'"

        return True, "Access granted"

    def get_tool_categories(self) -> List[str]:
        from sqlalchemy import distinct
        categories = self.db.query(distinct(AgentTool.category)).all()
        return [c[0] for c in categories]
