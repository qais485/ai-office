from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.analytics_service import AnalyticsService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/agent/{agent_id}")
async def get_agent_performance(agent_id: UUID, days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AnalyticsService(db)
    logger.debug("Retrieved performance for agent %s (days=%d)", agent_id, days)
    return service.get_agent_performance(agent_id, days)


@router.get("/company")
async def get_company_analytics(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AnalyticsService(db)
    return service.get_company_analytics(days)


@router.get("/ranking")
async def get_agent_ranking(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AnalyticsService(db)
    logger.debug("Retrieved agent ranking (days=%d)", days)
    return service.get_agent_ranking(days)


@router.get("/daily")
async def get_daily_stats(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = AnalyticsService(db)
    logger.debug("Retrieved daily stats (days=%d)", days)
    return service.get_daily_stats(days)
