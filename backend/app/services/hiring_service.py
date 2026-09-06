from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone

from app.models.agent import AIAgent, LifecycleStatus
from app.models.template import AgentTemplate
from app.models.room import OfficeRoom
from app.models.tool import AgentTool
from app.models.permission import Permission
from app.models.agent_permission import AgentPermission
from app.models.integration import Integration
from app.models.agent_integration import AgentIntegration
from app.services.permission_service import PermissionService
import logging

logger = logging.getLogger(__name__)


class HiringService:
    def __init__(self, db: Session):
        self.db = db
        self.permission_service = PermissionService(db)

    def get_templates(self, active_only: bool = True) -> List[AgentTemplate]:
        query = self.db.query(AgentTemplate)
        if active_only:
            query = query.filter(AgentTemplate.is_active == True)
        return query.all()

    def get_template(self, template_id: UUID) -> Optional[AgentTemplate]:
        return self.db.query(AgentTemplate).filter(AgentTemplate.id == template_id).first()

    def get_available_tools(self, template_id: UUID) -> List[AgentTool]:
        template = self.get_template(template_id)
        if not template or not template.default_tools:
            return []

        tool_names = template.default_tools
        return self.db.query(AgentTool).filter(
            AgentTool.name.in_(tool_names),
            AgentTool.is_active == True
        ).all()

    def get_available_permissions(self, template_id: UUID) -> List[Permission]:
        template = self.get_template(template_id)
        if not template or not template.default_permissions:
            return []

        perm_names = template.default_permissions
        return self.db.query(Permission).filter(Permission.name.in_(perm_names)).all()

    def get_available_integrations(self, template_id: UUID) -> List[Integration]:
        template = self.get_template(template_id)
        if not template or not template.default_tools:
            return []

        tool_names = template.default_tools
        tools = self.db.query(AgentTool).filter(
            AgentTool.name.in_(tool_names),
            AgentTool.is_active == True
        ).all()

        integration_ids = list(set(
            t.integration_id for t in tools if t.integration_id
        ))
        if not integration_ids:
            return []

        return self.db.query(Integration).filter(
            Integration.id.in_(integration_ids),
            Integration.is_active == True
        ).all()

    def create_agent_from_template(
        self,
        template_id: UUID,
        name: str,
        description: Optional[str] = None,
        room_id: Optional[UUID] = None,
        tool_ids: Optional[List[UUID]] = None,
        permission_ids: Optional[List[UUID]] = None,
        integration_ids: Optional[List[UUID]] = None,
        integration_account_ids: Optional[Dict[str, UUID]] = None,
        auto_create_room: bool = True,
        user_id: Optional[UUID] = None,
    ) -> AIAgent:
        """Create an agent from a template.

        Args:
            integration_account_ids: Optional dict mapping integration_id -> account_id
                for explicit account assignment. Ensures deterministic account selection.
            user_id: The user who owns this agent.
        """
        logger.info("Creating agent from template=%s name=%s", template_id, name)
        template = self.get_template(template_id)
        if not template:
            raise ValueError("Template not found")

        if not room_id and auto_create_room:
            room = self._create_default_room(name, user_id=user_id)
            room_id = room.id
        elif room_id:
            room = self.db.query(OfficeRoom).filter(OfficeRoom.id == room_id).first()
            if not room:
                raise ValueError("Room not found")
            # Verify room ownership if user_id is provided
            if user_id and room.user_id and room.user_id != user_id:
                raise ValueError("Room not found")

        agent = AIAgent(
            user_id=user_id,
            name=name,
            role=template.role,
            description=description or template.description,
            status="active",
            room_id=room_id,
            template_id=template_id,
            lifecycle_status=LifecycleStatus.ACTIVE,
            goals="|".join(template.default_goals) if template.default_goals else None,
            rules="|".join(template.default_rules) if template.default_rules else None,
            permissions="|".join(template.default_permissions) if template.default_permissions else None,
            tools="|".join(template.default_tools) if template.default_tools else None,
            hired_at=datetime.now(timezone.utc).isoformat(),
            last_active_at=datetime.now(timezone.utc).isoformat()
        )
        self.db.add(agent)
        self.db.flush()

        if tool_ids:
            tools = self.db.query(AgentTool).filter(AgentTool.id.in_(tool_ids)).all()
            agent.tools = "|".join([t.name for t in tools])

        if integration_ids:
            integrations = self.db.query(Integration).filter(Integration.id.in_(integration_ids)).all()
            for integration in integrations:
                # Get explicit account mapping if provided
                account_id = (integration_account_ids or {}).get(str(integration.id))

                agent_integration = AgentIntegration(
                    agent_id=agent.id,
                    integration_id=integration.id,
                    integration_account_id=UUID(account_id) if account_id else None,
                    capabilities="|".join(integration.capabilities.keys()) if integration.capabilities else None,
                    is_active=True
                )
                self.db.add(agent_integration)

        if permission_ids:
            permissions = self.db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
            agent.permissions = "|".join([p.name for p in permissions])
            self._set_selected_permissions(agent, permissions)
        else:
            self._set_default_permissions(agent, template)

        self.db.commit()
        self.db.refresh(agent)
        logger.info("Agent created: id=%s name=%s", agent.id, agent.name)
        return agent

    def _create_default_room(self, agent_name: str, user_id: Optional[UUID] = None) -> OfficeRoom:
        room = OfficeRoom(
            user_id=user_id,
            name=f"{agent_name}'s Office",
            description=f"Workspace for {agent_name}",
            status="available",
            room_type="workspace",
            capacity="1"
        )
        self.db.add(room)
        self.db.flush()
        return room

    def _set_selected_permissions(self, agent: AIAgent, permissions: List[Permission]):
        for permission in permissions:
            access_level = permission.default_status
            if permission.default_approval_required:
                access_level = "approval_required"

            agent_perm = AgentPermission(
                agent_id=agent.id,
                permission_id=permission.id,
                access_level=access_level,
                conditions=None,
                granted_by="template"
            )
            self.db.add(agent_perm)

    def _set_default_permissions(self, agent: AIAgent, template: AgentTemplate):
        if not template.default_permissions:
            return

        for perm_name in template.default_permissions:
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
                granted_by="template"
            )
            self.db.add(agent_perm)

    def update_agent_lifecycle(self, agent_id: UUID, new_status: LifecycleStatus) -> Optional[AIAgent]:
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return None

        valid_transitions = {
            LifecycleStatus.DRAFT: [LifecycleStatus.ACTIVE],
            LifecycleStatus.ACTIVE: [LifecycleStatus.PAUSED, LifecycleStatus.DISABLED, LifecycleStatus.ERROR],
            LifecycleStatus.PAUSED: [LifecycleStatus.ACTIVE, LifecycleStatus.DISABLED],
            LifecycleStatus.INACTIVE: [LifecycleStatus.ACTIVE],
            LifecycleStatus.ERROR: [LifecycleStatus.ACTIVE, LifecycleStatus.DISABLED],
            LifecycleStatus.DISABLED: [LifecycleStatus.ACTIVE],
            LifecycleStatus.ARCHIVED: []
        }

        if new_status not in valid_transitions.get(agent.lifecycle_status, []):
            raise ValueError(f"Cannot transition from {agent.lifecycle_status} to {new_status}")

        now = datetime.now(timezone.utc).isoformat()
        old_status = agent.lifecycle_status

        if new_status == LifecycleStatus.ACTIVE:
            agent.status = "active"
            agent.last_active_at = now
            agent.last_error = None
        elif new_status == LifecycleStatus.PAUSED:
            agent.status = "inactive"
            agent.paused_at = now
        elif new_status == LifecycleStatus.DISABLED:
            agent.status = "inactive"
            agent.disabled_at = now
        elif new_status == LifecycleStatus.ERROR:
            agent.status = "inactive"
        elif new_status == LifecycleStatus.ARCHIVED:
            agent.status = "inactive"
            agent.archived_at = now

        agent.lifecycle_status = new_status
        self.db.commit()
        self.db.refresh(agent)

        # Sync agent runtime with lifecycle changes
        self._sync_agent_runtime(agent, old_status, new_status)

        return agent

    def pause_agent(self, agent_id: UUID) -> Optional[AIAgent]:
        return self.update_agent_lifecycle(agent_id, LifecycleStatus.PAUSED)

    def resume_agent(self, agent_id: UUID) -> Optional[AIAgent]:
        return self.update_agent_lifecycle(agent_id, LifecycleStatus.ACTIVE)

    def disable_agent(self, agent_id: UUID, reason: Optional[str] = None) -> Optional[AIAgent]:
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return None
        
        agent = self.update_agent_lifecycle(agent_id, LifecycleStatus.DISABLED)
        if agent and reason:
            agent.disabled_reason = reason
            self.db.commit()
            self.db.refresh(agent)
        return agent

    def archive_agent(self, agent_id: UUID) -> Optional[AIAgent]:
        return self.update_agent_lifecycle(agent_id, LifecycleStatus.ARCHIVED)

    def set_error(self, agent_id: UUID, error_message: str) -> Optional[AIAgent]:
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return None
        
        agent.lifecycle_status = LifecycleStatus.ERROR
        agent.status = "inactive"
        agent.last_error = error_message
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def restart_agent(self, agent_id: UUID) -> Optional[AIAgent]:
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return None
        
        if agent.lifecycle_status != LifecycleStatus.ERROR:
            raise ValueError("Can only restart agents in error state")
        
        return self.update_agent_lifecycle(agent_id, LifecycleStatus.ACTIVE)

    def _sync_agent_runtime(self, agent: AIAgent, old_status: LifecycleStatus, new_status: LifecycleStatus) -> None:
        """Synchronize agent runtime with lifecycle status changes.

        Called after every lifecycle transition. Starts/stops the agent loop
        as needed. Errors are logged but never propagated to the caller.
        """
        try:
            import asyncio
            from app.services.agent_runtime import agent_runtime

            agent_id = str(agent.id)

            if new_status == LifecycleStatus.ACTIVE:
                loop = agent_runtime.get_loop(agent_id)
                if loop and loop.is_running:
                    return

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(agent_runtime.activate_agent(agent_id))
                    else:
                        loop.run_until_complete(agent_runtime.activate_agent(agent_id))
                except RuntimeError:
                    asyncio.run(agent_runtime.activate_agent(agent_id))

                logger.info(f"Agent {agent.name} activated in runtime (lifecycle: {old_status.value} -> {new_status.value})")

            elif new_status in (LifecycleStatus.PAUSED, LifecycleStatus.DISABLED, LifecycleStatus.ERROR, LifecycleStatus.ARCHIVED):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(agent_runtime.deactivate_agent(agent_id))
                    else:
                        loop.run_until_complete(agent_runtime.deactivate_agent(agent_id))
                except RuntimeError:
                    asyncio.run(agent_runtime.deactivate_agent(agent_id))

                logger.info(f"Agent {agent.name} deactivated in runtime (lifecycle: {old_status.value} -> {new_status.value})")

        except Exception as e:
            logger.error(f"Failed to sync agent runtime for {agent.name}: {e}", exc_info=True)

    def update_last_active(self, agent_id: UUID) -> Optional[AIAgent]:
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return None
        
        agent.last_active_at = datetime.now(timezone.utc).isoformat()
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def delete_agent(self, agent_id: UUID) -> bool:
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return False

        self.db.query(AgentPermission).filter(AgentPermission.agent_id == agent_id).delete()
        self.db.query(AgentIntegration).filter(AgentIntegration.agent_id == agent_id).delete()

        room = None
        if agent.room_id:
            room = self.db.query(OfficeRoom).filter(OfficeRoom.id == agent.room_id).first()

        self.db.delete(agent)
        self.db.commit()
        return True

    def get_agent_with_tools(self, agent_id: UUID) -> dict:
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            return {}

        tool_names = agent.tools.split("|") if agent.tools else []
        tools = self.db.query(AgentTool).filter(AgentTool.name.in_(tool_names)).all() if tool_names else []

        perm_names = agent.permissions.split("|") if agent.permissions else []
        permissions = self.db.query(Permission).filter(Permission.name.in_(perm_names)).all() if perm_names else []

        agent_perms = self.db.query(AgentPermission).filter(AgentPermission.agent_id == agent_id).all()
        perm_ids = [ap.permission_id for ap in agent_perms]
        perm_objects = self.db.query(Permission).filter(Permission.id.in_(perm_ids)).all() if perm_ids else []
        perm_map = {p.id: p for p in perm_objects}

        perm_details = []
        for ap in agent_perms:
            perm = perm_map.get(ap.permission_id)
            if perm:
                perm_details.append({
                    "name": perm.name,
                    "category": perm.category,
                    "risk_level": perm.risk_level,
                    "access_level": ap.access_level,
                    "conditions": ap.conditions
                })

        template = None
        if agent.template_id:
            template = self.db.query(AgentTemplate).filter(AgentTemplate.id == agent.template_id).first()

        room = None
        if agent.room_id:
            room = self.db.query(OfficeRoom).filter(OfficeRoom.id == agent.room_id).first()

        agent_integrations = self.db.query(AgentIntegration).filter(AgentIntegration.agent_id == agent_id).all()
        integration_ids = [ai.integration_id for ai in agent_integrations]
        integrations = self.db.query(Integration).filter(Integration.id.in_(integration_ids)).all() if integration_ids else []

        return {
            "agent": agent,
            "template": template,
            "room": room,
            "tools": tools,
            "permissions": permissions,
            "permission_details": perm_details,
            "integrations": integrations
        }
