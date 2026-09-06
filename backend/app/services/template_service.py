from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.template import AgentTemplate
from app.schemas.template import AgentTemplateCreate, AgentTemplateUpdate
import logging

logger = logging.getLogger(__name__)


class TemplateService:
    def __init__(self, db: Session):
        self.db = db

    def get_templates(self, active_only: bool = False) -> List[AgentTemplate]:
        query = self.db.query(AgentTemplate)
        if active_only:
            query = query.filter(AgentTemplate.is_active == True)
        return query.all()

    def get_template(self, template_id: UUID) -> Optional[AgentTemplate]:
        return self.db.query(AgentTemplate).filter(AgentTemplate.id == template_id).first()

    def create_template(self, data: AgentTemplateCreate) -> AgentTemplate:
        logger.info("Creating template: %s", data.name if hasattr(data, 'name') else 'new')
        template = AgentTemplate(**data.model_dump())
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def update_template(self, template_id: UUID, data: AgentTemplateUpdate) -> Optional[AgentTemplate]:
        template = self.get_template(template_id)
        if template:
            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(template, key, value)
            self.db.commit()
            self.db.refresh(template)
        return template

    def delete_template(self, template_id: UUID) -> bool:
        template = self.get_template(template_id)
        if template:
            self.db.delete(template)
            self.db.commit()
            return True
        return False
