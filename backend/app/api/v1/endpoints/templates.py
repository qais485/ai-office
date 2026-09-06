from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.template import AgentTemplateCreate, AgentTemplateUpdate, AgentTemplateResponse
from app.services.template_service import TemplateService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[AgentTemplateResponse])
async def get_templates(active_only: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = TemplateService(db)
    templates = service.get_templates(active_only=active_only)
    logger.debug("Listed %d templates", len(templates))
    return templates


@router.get("/{template_id}", response_model=AgentTemplateResponse)
async def get_template(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = TemplateService(db)
    template = service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    logger.debug("Retrieved template %s", template_id)
    return template


@router.post("/", response_model=AgentTemplateResponse)
async def create_template(template: AgentTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = TemplateService(db)
    created = service.create_template(template)
    logger.info("Created template %s", created.id)
    return created


@router.put("/{template_id}", response_model=AgentTemplateResponse)
async def update_template(template_id: str, template: AgentTemplateUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = TemplateService(db)
    updated = service.update_template(template_id, template)
    if not updated:
        raise HTTPException(status_code=404, detail="Template not found")
    logger.info("Updated template %s", template_id)
    return updated


@router.delete("/{template_id}")
async def delete_template(template_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = TemplateService(db)
    deleted = service.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    logger.info("Deleted template %s", template_id)
    return {"detail": "Template deleted"}
