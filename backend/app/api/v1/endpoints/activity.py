from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.activity import ActivityCreate, ActivityResponse
from app.services.activity_service import ActivityService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[ActivityResponse])
def list_activities(limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = ActivityService(db)
    activities = service.get_all_activities(limit=limit)
    logger.debug("Listed %d activities", len(activities))
    return activities


@router.get("/agent/{agent_id}", response_model=list[ActivityResponse])
def get_agent_activities(agent_id: UUID, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = ActivityService(db)
    return service.get_agent_activities(agent_id, limit=limit)


@router.post("/", response_model=ActivityResponse, status_code=201)
def log_activity(data: ActivityCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = ActivityService(db)
    created = service.log_activity(data)
    logger.info("Created activity %s", created.id)
    return created
