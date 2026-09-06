from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.permission import (
    PermissionCreate, PermissionUpdate, PermissionResponse,
    AgentPermissionCreate, AgentPermissionUpdate, AgentPermissionResponse,
    AgentPermissionWithDetails, PermissionCheckRequest, PermissionCheckResponse
)
from app.services.permission_service import PermissionService
from app.api.deps import require_role, get_current_active_user
from app.models.user import User, UserRole

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[PermissionResponse])
async def get_permissions(
    active_only: bool = False,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = PermissionService(db)
    perms = service.get_permissions(active_only=active_only, category=category)
    logger.debug("Listed %d permissions", len(perms))
    return perms


@router.get("/categories", response_model=list[str])
async def get_permission_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = PermissionService(db)
    return service.get_permission_categories()


@router.get("/{permission_id}", response_model=PermissionResponse)
async def get_permission(
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = PermissionService(db)
    permission = service.get_permission(permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    logger.debug("Retrieved permission %s", permission_id)
    return permission


@router.post("/", response_model=PermissionResponse)
async def create_permission(
    permission: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))
):
    service = PermissionService(db)
    existing = service.get_permission_by_name(permission.name)
    if existing:
        raise HTTPException(status_code=400, detail="Permission with this name already exists")
    created = service.create_permission(permission)
    logger.info("Created permission %s", created.id)
    return created


@router.put("/{permission_id}", response_model=PermissionResponse)
async def update_permission(
    permission_id: UUID,
    permission: PermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))
):
    service = PermissionService(db)
    updated = service.update_permission(permission_id, permission)
    if not updated:
        raise HTTPException(status_code=404, detail="Permission not found")
    logger.info("Updated permission %s", permission_id)
    return updated


@router.delete("/{permission_id}")
async def delete_permission(
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))
):
    service = PermissionService(db)
    deleted = service.delete_permission(permission_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Permission not found")
    logger.info("Deleted permission %s", permission_id)
    return {"detail": "Permission deleted"}


@router.get("/agent/{agent_id}", response_model=list[AgentPermissionWithDetails])
async def get_agent_permissions(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = PermissionService(db)
    return service.get_agent_permissions_with_details(agent_id)


@router.post("/agent/{agent_id}", response_model=AgentPermissionResponse)
async def set_agent_permission(
    agent_id: UUID,
    permission: AgentPermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))
):
    service = PermissionService(db)
    result = service.set_agent_permission(agent_id, permission, granted_by="ceo")
    logger.info("Granted permission to agent %s", agent_id)
    return result


@router.put("/agent/{agent_id}/{permission_id}", response_model=AgentPermissionResponse)
async def update_agent_permission(
    agent_id: UUID,
    permission_id: UUID,
    data: AgentPermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = PermissionService(db)
    agent_perm = service.db.query(AgentPermission).filter(
        AgentPermission.agent_id == agent_id,
        AgentPermission.permission_id == permission_id
    ).first()
    
    if not agent_perm:
        raise HTTPException(status_code=404, detail="Agent permission not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent_perm, key, value)
    service.db.commit()
    service.db.refresh(agent_perm)
    return agent_perm


@router.delete("/agent/{agent_id}/{permission_id}")
async def delete_agent_permission(
    agent_id: UUID,
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = PermissionService(db)
    deleted = service.delete_agent_permission(agent_id, permission_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent permission not found")
    logger.info("Revoked permission %s from agent %s", permission_id, agent_id)
    return {"detail": "Agent permission deleted"}


@router.post("/agent/{agent_id}/revoke-all")
async def revoke_all_agent_permissions(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO, UserRole.ADMIN))
):
    service = PermissionService(db)
    service.revoke_all_agent_permissions(agent_id)
    logger.info("Revoked all permissions from agent %s", agent_id)
    return {"detail": "All agent permissions revoked"}


@router.post("/check", response_model=PermissionCheckResponse)
async def check_permission(
    data: PermissionCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = PermissionService(db)
    has_perm, access_level, message = service.check_permission(data.agent_id, data.permission_name)
    logger.debug("Permission check for agent %s: %s", data.agent_id, has_perm)
    return PermissionCheckResponse(
        has_permission=has_perm,
        access_level=access_level,
        message=message,
        requires_approval=access_level == "approval_required"
    )


@router.get("/{permission_id}/agents", response_model=list[dict])
async def get_permission_agents(
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    service = PermissionService(db)
    permission = service.get_permission(permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    return service.get_agents_with_permission(permission.name)
