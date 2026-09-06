from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from app.services.agent_service import AgentService
from app.api.deps import get_current_active_user, require_role
from app.models.user import User, UserRole

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[AgentResponse])
def get_agents(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agent_service = AgentService(db)
    agents = agent_service.get_agents(user_id=current_user.id)
    logger.debug("Listed %d agents for user %s", len(agents), current_user.id)
    return agents


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agent_service = AgentService(db)
    agent = agent_service.get_agent(agent_id, user_id=current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    logger.debug("Retrieved agent %s for user %s", agent_id, current_user.id)
    return agent


@router.post("/", response_model=AgentResponse)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agent_service = AgentService(db)
    created = agent_service.create_agent(agent, user_id=current_user.id)
    logger.info("Created agent %s for user %s", created.id, current_user.id)
    return created


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: str, agent: AgentUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agent_service = AgentService(db)
    updated = agent_service.update_agent(agent_id, agent, user_id=current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Agent not found")
    logger.info("Updated agent %s for user %s", agent_id, current_user.id)
    return updated


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    agent_service = AgentService(db)
    deleted = agent_service.delete_agent(agent_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    logger.info("Deleted agent %s for user %s", agent_id, current_user.id)
    return {"detail": "Agent deleted"}
