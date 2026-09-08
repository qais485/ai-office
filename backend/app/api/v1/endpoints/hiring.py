from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database.session import get_db
from app.services.hiring_service import HiringService
from app.api.deps import get_current_active_user
from app.models.user import User
from app.schemas.template import AgentTemplateResponse
from app.schemas.tool import ToolResponse
from app.schemas.permission import PermissionResponse
from app.schemas.integration import IntegrationResponse

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class HireAgentRequest(BaseModel):
    template_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    room_id: Optional[UUID] = None
    tool_ids: Optional[List[UUID]] = None
    permission_ids: Optional[List[UUID]] = None
    integration_ids: Optional[List[UUID]] = None
    integration_account_ids: Optional[dict] = None
    auto_create_room: bool = True


class AgentLifecycleRequest(BaseModel):
    action: str = Field(..., pattern="^(pause|resume|disable|archive|restart)$")
    reason: Optional[str] = None


class AgentDeleteRequest(BaseModel):
    pass


@router.get("/templates", response_model=List[AgentTemplateResponse])
async def get_templates(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = HiringService(db)
    return service.get_templates()


@router.get("/templates/{template_id}", response_model=AgentTemplateResponse)
async def get_template(template_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = HiringService(db)
    template = service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("/templates/{template_id}/tools", response_model=List[ToolResponse])
async def get_template_tools(template_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = HiringService(db)
    return service.get_available_tools(template_id)


@router.get("/templates/{template_id}/permissions", response_model=List[PermissionResponse])
async def get_template_permissions(template_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = HiringService(db)
    return service.get_available_permissions(template_id)


@router.get("/templates/{template_id}/integrations", response_model=List[IntegrationResponse])
async def get_template_integrations(template_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = HiringService(db)
    return service.get_available_integrations(template_id)


@router.post("/hire")
async def hire_agent(request: HireAgentRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = HiringService(db)
    try:
        agent = service.create_agent_from_template(
            template_id=request.template_id,
            name=request.name,
            description=request.description,
            room_id=request.room_id,
            tool_ids=request.tool_ids,
            permission_ids=request.permission_ids,
            integration_ids=request.integration_ids,
            integration_account_ids=request.integration_account_ids,
            auto_create_room=request.auto_create_room,
            user_id=current_user.id,
        )
        logger.info("Hired agent %s from template %s for user %s", agent.id, request.template_id, current_user.id)
        return {
            "message": f"Successfully hired {agent.name}",
            "agent_id": str(agent.id),
            "lifecycle_status": agent.lifecycle_status.value if agent.lifecycle_status else "active"
        }
    except ValueError as e:
        logger.error("Failed to hire agent: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{agent_id}/lifecycle")
async def update_lifecycle(agent_id: UUID, request: AgentLifecycleRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = HiringService(db)
    try:
        from app.models.agent import LifecycleStatus
        
        # Verify agent ownership
        agent = service.get_agent_with_tools(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        if agent["agent"].user_id and agent["agent"].user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        if request.action == "restart":
            agent_result = service.restart_agent(agent_id)
            if not agent_result:
                raise HTTPException(status_code=404, detail="Agent not found")
            return {
                "message": "Agent restarted successfully",
                "lifecycle_status": agent_result.lifecycle_status.value
            }
        
        action_map = {
            "pause": LifecycleStatus.PAUSED,
            "resume": LifecycleStatus.ACTIVE,
            "disable": LifecycleStatus.DISABLED,
            "archive": LifecycleStatus.ARCHIVED
        }

        if request.action not in action_map:
            raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")

        if request.action == "disable":
            agent_result = service.disable_agent(agent_id, reason=request.reason)
        else:
            agent_result = service.update_agent_lifecycle(agent_id, action_map[request.action])
        
        if not agent_result:
            raise HTTPException(status_code=404, detail="Agent not found")

        logger.info("Updated lifecycle for agent %s to %s for user %s", agent_id, request.action, current_user.id)
        return {
            "message": f"Agent {request.action}d successfully",
            "lifecycle_status": agent_result.lifecycle_status.value
        }
    except ValueError as e:
        logger.error("Failed to update lifecycle for agent %s: %s", agent_id, e)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{agent_id}")
async def delete_agent(agent_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from app.services.agent_service import AgentService
    agent_service = AgentService(db)
    agent = agent_service.get_agent(agent_id, user_id=current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    service = HiringService(db)
    success = service.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    logger.info("Deleted agent %s for user %s", agent_id, current_user.id)
    return {"message": "Agent deleted successfully"}


@router.get("/{agent_id}/details")
async def get_agent_details(agent_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from app.services.agent_service import AgentService
    agent_service = AgentService(db)
    agent = agent_service.get_agent(agent_id, user_id=current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    service = HiringService(db)
    details = service.get_agent_with_tools(agent_id)
    if not details:
        raise HTTPException(status_code=404, detail="Agent not found")
    logger.debug("Retrieved details for agent %s for user %s", agent_id, current_user.id)

    agent = details["agent"]
    return {
        "agent": {
            "id": str(agent.id),
            "name": agent.name,
            "role": agent.role,
            "description": agent.description,
            "status": agent.status,
            "lifecycle_status": agent.lifecycle_status.value if agent.lifecycle_status else None,
            "hired_at": agent.hired_at,
            "last_active_at": agent.last_active_at,
            "paused_at": agent.paused_at,
            "disabled_at": agent.disabled_at,
            "disabled_reason": agent.disabled_reason,
            "last_error": agent.last_error,
            "archived_at": agent.archived_at,
            "room_id": str(agent.room_id) if agent.room_id else None
        },
        "template": {
            "id": str(details["template"].id),
            "name": details["template"].name,
            "role": details["template"].role
        } if details["template"] else None,
        "room": {
            "id": str(details["room"].id),
            "name": details["room"].name,
            "status": details["room"].status
        } if details["room"] else None,
        "tools": [
            {
                "id": str(t.id),
                "name": t.name,
                "display_name": t.display_name,
                "risk_level": t.risk_level,
                "requires_approval": t.requires_approval
            }
            for t in details["tools"]
        ],
        "permission_details": details["permission_details"]
    }
