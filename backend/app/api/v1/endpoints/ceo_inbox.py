from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.ceo_inbox_service import CEOInboxService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class InboxActionRequest(BaseModel):
    notes: Optional[str] = None


@router.get("/")
async def get_inbox_items(
    unread_only: bool = False,
    filter_type: Optional[str] = None,
    filter_priority: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = CEOInboxService(db)
    return service.get_inbox_items(
        current_user.id,
        unread_only=unread_only,
        filter_type=filter_type,
        filter_priority=filter_priority,
    )


@router.get("/counts")
async def get_inbox_counts(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = CEOInboxService(db)
    return service.get_inbox_counts(current_user.id)


@router.post("/{item_type}/{item_id}/approve")
async def approve_item(
    item_type: str,
    item_id: UUID,
    request: InboxActionRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = CEOInboxService(db)
    notes = request.notes if request else None
    result = service.approve_item(str(item_id), item_type, current_user.id, notes)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    logger.info("CEO approved %s %s", item_type, item_id)
    return result


@router.post("/{item_type}/{item_id}/reject")
async def reject_item(
    item_type: str,
    item_id: UUID,
    request: InboxActionRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = CEOInboxService(db)
    notes = request.notes if request else None
    result = service.reject_item(str(item_id), item_type, current_user.id, notes)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    logger.info("CEO rejected %s %s", item_type, item_id)
    return result


@router.post("/{item_type}/{item_id}/dismiss")
async def dismiss_item(
    item_type: str,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = CEOInboxService(db)
    result = service.dismiss_item(str(item_id), item_type, current_user.id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    logger.info("CEO dismissed %s %s", item_type, item_id)
    return result


@router.post("/{item_type}/{item_id}/archive")
async def archive_item(
    item_type: str,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = CEOInboxService(db)
    result = service.archive_item(str(item_id), item_type, current_user.id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    logger.info("CEO archived %s %s", item_type, item_id)
    return result


@router.post("/{item_type}/{item_id}/resolve")
async def resolve_item(
    item_type: str,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = CEOInboxService(db)
    result = service.resolve_item(str(item_id), item_type, current_user.id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    logger.info("CEO resolved %s %s", item_type, item_id)
    return result


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = CEOInboxService(db)
    success = service.mark_notification_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}


@router.post("/read-all")
async def mark_all_notifications_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = CEOInboxService(db)
    count = service.mark_all_notifications_read(current_user.id)
    return {"marked": count}
