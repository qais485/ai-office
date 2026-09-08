from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.tool import (
    ToolCreate, ToolUpdate, ToolResponse, ToolWithActionsResponse,
    ToolActionCreate, ToolActionUpdate, ToolActionResponse,
    ToolPermissionCreate, ToolPermissionResponse,
    AgentToolAssignmentCreate, AgentToolAssignmentResponse
)
from app.services.tool_service import ToolService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[ToolResponse])
async def get_tools(
    active_only: bool = False,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    tools = service.get_tools(active_only=active_only, category=category)
    logger.debug("Listed %d tools", len(tools))
    return tools


@router.get("/categories", response_model=list[str])
async def get_tool_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    return service.get_tool_categories()


@router.get("/template/{template_id}", response_model=list[ToolResponse])
async def get_tools_for_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    return service.get_tools_for_template(template_id)


@router.get("/{tool_id}", response_model=ToolWithActionsResponse)
async def get_tool(
    tool_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    result = service.get_tool_with_actions(tool_id)
    if not result:
        raise HTTPException(status_code=404, detail="Tool not found")
    logger.debug("Retrieved tool %s", tool_id)
    
    tool = result["tool"]
    actions = result["actions"]
    permissions = result["permissions"]
    
    return ToolWithActionsResponse(
        id=tool.id,
        name=tool.name,
        display_name=tool.display_name,
        description=tool.description,
        category=tool.category,
        integration_id=tool.integration_id,
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
        risk_level=tool.risk_level,
        requires_approval=tool.requires_approval,
        is_active=tool.is_active,
        version=tool.version,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
        actions=[ToolActionResponse.model_validate(a) for a in actions],
        permissions=[ToolPermissionResponse.model_validate(p) for p in permissions]
    )


@router.post("/", response_model=ToolResponse)
async def create_tool(
    tool: ToolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    created = service.create_tool(tool)
    logger.info("Created tool %s", created.id)
    return created


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: UUID,
    tool: ToolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    updated = service.update_tool(tool_id, tool)
    if not updated:
        raise HTTPException(status_code=404, detail="Tool not found")
    logger.info("Updated tool %s", tool_id)
    return updated


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    deleted = service.delete_tool(tool_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tool not found")
    logger.info("Deleted tool %s", tool_id)
    return {"detail": "Tool deleted"}


@router.get("/agent/{agent_id}", response_model=list[ToolResponse])
async def get_agent_tools(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    return service.get_agent_tools(agent_id)


@router.post("/agent/{agent_id}/assign", response_model=AgentToolAssignmentResponse)
async def assign_tool_to_agent(
    agent_id: UUID,
    data: AgentToolAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    result = service.assign_tool_to_agent(agent_id, data.tool_id, data.config)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to assign tool")
    logger.info("Assigned tool %s to agent %s", data.tool_id, agent_id)
    return result


@router.delete("/agent/{agent_id}/remove")
async def remove_tool_from_agent(
    agent_id: UUID,
    tool_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    success = service.remove_tool_from_agent(agent_id, tool_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tool assignment not found")
    logger.info("Removed tool %s from agent %s", tool_id, agent_id)
    return {"detail": "Tool removed from agent"}


@router.get("/{tool_id}/agents", response_model=list[dict])
async def get_tool_agents(
    tool_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    return service.get_tool_agents(tool_id)


@router.get("/validate/{agent_id}/{tool_name}")
async def validate_tool_access(
    agent_id: UUID,
    tool_name: str,
    action_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = ToolService(db)
    has_access, message = service.validate_tool_access(agent_id, tool_name, action_name)
    return {"has_access": has_access, "message": message}
