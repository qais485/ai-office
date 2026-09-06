from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[NotificationResponse])
def get_notifications(unread_only: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = NotificationService(db)
    notifications = service.get_notifications(current_user.id, unread_only=unread_only)
    logger.debug("Listed %d notifications", len(notifications))
    return notifications


@router.get("/unread-count")
def get_unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = NotificationService(db)
    count = service.get_unread_count(current_user.id)
    return {"count": count}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = NotificationService(db)
    notification = service.get_notification(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    updated = service.mark_as_read(notification_id)
    logger.info("Marked notification %s as read", notification_id)
    return updated


@router.post("/read-all")
def mark_all_as_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = NotificationService(db)
    count = service.mark_all_as_read(current_user.id)
    return {"marked": count}


@router.delete("/{notification_id}")
def delete_notification(notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    service = NotificationService(db)
    notification = service.get_notification(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    deleted = service.delete_notification(notification_id)
    logger.info("Deleted notification %s", notification_id)
    return {"detail": "Notification deleted"}
