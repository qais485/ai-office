from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.dashboard_service import DashboardService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = DashboardService(db)
    logger.debug("User %s requested dashboard summary", current_user.id)
    return service.get_ceo_summary(user_id=current_user.id)


@router.get("/agents")
async def get_agent_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = DashboardService(db)
    logger.debug("User %s requested agent overview", current_user.id)
    return service.get_agent_status_overview(user_id=current_user.id)


@router.get("/activity")
async def get_recent_activity(limit: int = 20, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = DashboardService(db)
    return service.get_recent_activity(limit=limit, user_id=current_user.id)


@router.get("/performance")
async def get_performance_metrics(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = DashboardService(db)
    return service.get_performance_metrics(user_id=current_user.id)
