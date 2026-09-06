from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.dashboard_service import DashboardService
from app.api.deps import get_current_active_user
from app.models.user import User, UserRole

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def require_ceo_or_admin(current_user: User):
    if current_user.role not in (UserRole.CEO.value, UserRole.ADMIN.value):
        raise HTTPException(status_code=403, detail="CEO or Admin role required")


@router.get("/summary")
async def get_dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    require_ceo_or_admin(current_user)
    service = DashboardService(db)
    logger.debug("CEO %s requested dashboard summary", current_user.id)
    return service.get_ceo_summary(user_id=current_user.id, role=current_user.role)


@router.get("/agents")
async def get_agent_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    require_ceo_or_admin(current_user)
    service = DashboardService(db)
    logger.debug("CEO %s requested agent overview", current_user.id)
    return service.get_agent_status_overview(user_id=current_user.id, role=current_user.role)


@router.get("/activity")
async def get_recent_activity(limit: int = 20, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    require_ceo_or_admin(current_user)
    service = DashboardService(db)
    return service.get_recent_activity(limit=limit, user_id=current_user.id, role=current_user.role)


@router.get("/performance")
async def get_performance_metrics(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    require_ceo_or_admin(current_user)
    service = DashboardService(db)
    return service.get_performance_metrics(user_id=current_user.id, role=current_user.role)
