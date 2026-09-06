from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.knowledge import (
    KnowledgeCreate, KnowledgeUpdate, KnowledgeResponse,
    SearchRequest, BulkAccessRequest, AgentKnowledgeAccessResponse,
)
from app.services.knowledge_service import KnowledgeService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[KnowledgeResponse])
async def get_knowledge(
    category: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = KnowledgeService(db)
    sources = service.get_sources(category=category, source_type=source_type, status=status, search=search, user_id=current_user.id)
    logger.debug("Listed %d knowledge sources for user %s", len(sources), current_user.id)
    return sources


@router.get("/stats")
async def get_knowledge_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    return service.get_knowledge_stats(user_id=current_user.id)


@router.post("/search")
async def search_knowledge(request: SearchRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    return service.search_knowledge(request.query, request.category, request.limit, user_id=current_user.id)


@router.get("/{knowledge_id}", response_model=KnowledgeResponse)
async def get_knowledge_source(knowledge_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    source = service.get_source(knowledge_id, user_id=current_user.id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    logger.debug("Retrieved knowledge source %s for user %s", knowledge_id, current_user.id)
    return source


@router.post("/", response_model=KnowledgeResponse)
async def create_knowledge(knowledge: KnowledgeCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    created = service.create_source(knowledge, created_by=current_user.id)
    logger.info("Created knowledge source %s for user %s", created.id, current_user.id)
    return created


@router.put("/{knowledge_id}", response_model=KnowledgeResponse)
async def update_knowledge(knowledge_id: UUID, knowledge: KnowledgeUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    updated = service.update_source(knowledge_id, knowledge, user_id=current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    logger.info("Updated knowledge source %s for user %s", knowledge_id, current_user.id)
    return updated


@router.delete("/{knowledge_id}")
async def delete_knowledge(knowledge_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    deleted = service.delete_source(knowledge_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    logger.info("Deleted knowledge source %s for user %s", knowledge_id, current_user.id)
    return {"detail": "Knowledge source deleted"}


@router.post("/{knowledge_id}/access/{agent_id}")
async def grant_agent_access(
    knowledge_id: UUID,
    agent_id: UUID,
    access_level: str = "read",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = KnowledgeService(db)
    # Verify knowledge source ownership
    source = service.get_source(knowledge_id, user_id=current_user.id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    # Verify agent ownership
    from app.services.agent_service import AgentService
    agent_service = AgentService(db)
    agent = agent_service.get_agent(agent_id, user_id=current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    service.grant_access(agent_id, knowledge_id, access_level, granted_by=str(current_user.id))
    logger.info("Granted %s access to knowledge %s for agent %s", access_level, knowledge_id, agent_id)
    return {"detail": "Access granted"}


@router.delete("/{knowledge_id}/access/{agent_id}")
async def revoke_agent_access(knowledge_id: UUID, agent_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    # Verify knowledge source ownership
    source = service.get_source(knowledge_id, user_id=current_user.id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    revoked = service.revoke_access(agent_id, knowledge_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Access not found")
    logger.info("Revoked access to knowledge %s for agent %s", knowledge_id, agent_id)
    return {"detail": "Access revoked"}


@router.get("/{knowledge_id}/agents", response_model=list[AgentKnowledgeAccessResponse])
async def get_knowledge_agents(knowledge_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    source = service.get_source(knowledge_id, user_id=current_user.id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    return service.get_knowledge_agents(knowledge_id)


@router.post("/bulk-access")
async def bulk_grant_access(request: BulkAccessRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    # Verify agent ownership
    from app.services.agent_service import AgentService
    agent_service = AgentService(db)
    agent = agent_service.get_agent(request.agent_id, user_id=current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    count = service.bulk_grant_access(request.agent_id, request.knowledge_ids, request.access_level, granted_by=str(current_user.id))
    return {"detail": f"Access granted to {count} knowledge sources"}


@router.get("/agent/{agent_id}/context")
async def get_agent_knowledge_context(agent_id: UUID, query: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    # Verify agent ownership
    from app.services.agent_service import AgentService
    agent_service = AgentService(db)
    agent = agent_service.get_agent(agent_id, user_id=current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return service.get_agent_knowledge_context(agent_id, query)


@router.post("/{knowledge_id}/reprocess")
async def reprocess_knowledge(knowledge_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = KnowledgeService(db)
    success = service.reprocess_embeddings(knowledge_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reprocess embeddings")
    logger.info("Reprocessed embeddings for knowledge %s for user %s", knowledge_id, current_user.id)
    return {"detail": "Embeddings reprocessed successfully"}
