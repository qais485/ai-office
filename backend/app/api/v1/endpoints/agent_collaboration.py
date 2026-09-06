from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.services.agent_collaboration_service import AgentCollaborationService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateCollaborationRequest(BaseModel):
    from_agent_id: UUID
    to_agent_id: UUID
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    input_json: Optional[dict] = None


@router.post("/create-task")
async def create_collaboration_task(request: CreateCollaborationRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AgentCollaborationService(db)
    result = service.create_collaboration_task(
        from_agent_id=request.from_agent_id,
        to_agent_id=request.to_agent_id,
        title=request.title,
        description=request.description,
        priority=request.priority,
        input_json=request.input_json
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    logger.info("Created collaboration task from agent %s to agent %s", request.from_agent_id, request.to_agent_id)
    return result


@router.get("/agent/{agent_id}")
async def get_agent_collaborations(agent_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AgentCollaborationService(db)
    return service.get_agent_collaborations(agent_id)


@router.get("/stats")
async def get_collaboration_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AgentCollaborationService(db)
    stats = service.get_collaboration_stats()
    logger.debug("Retrieved collaboration stats")
    return stats


@router.get("/check/{from_agent_id}/{to_agent_id}")
async def can_agents_collaborate(from_agent_id: UUID, to_agent_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AgentCollaborationService(db)
    result = service.can_agents_collaborate(from_agent_id, to_agent_id)
    logger.debug("Checked collaboration between agents %s and %s: %s", from_agent_id, to_agent_id, result.get("can_collaborate"))
    return result


@router.get("/partners/{agent_id}")
async def get_available_partners(agent_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AgentCollaborationService(db)
    return service.get_available_collaboration_partners(agent_id)
