import asyncio
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.notification import Notification
from app.schemas.notification import NotificationCreate

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _fire_async(coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            asyncio.run(coro)

    def get_notifications(self, user_id: UUID, unread_only: bool = False) -> List[Notification]:
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return query.order_by(Notification.created_at.desc()).all()

    def get_notification(self, notification_id: UUID) -> Optional[Notification]:
        return self.db.query(Notification).filter(Notification.id == notification_id).first()

    def create_notification(self, data: NotificationCreate) -> Notification:
        notification = Notification(**data.model_dump())
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        try:
            from app.events.publisher import publish_notification_created
            self._fire_async(
                publish_notification_created(
                    notification_id=notification.id,
                    user_id=notification.user_id,
                    notification_type=notification.type,
                    title=notification.title,
                    message=notification.message or "",
                )
            )
        except Exception as e:
            logger.warning("Failed to publish notification event", exc_info=True)

        return notification

    def mark_as_read(self, notification_id: UUID) -> Optional[Notification]:
        notification = self.get_notification(notification_id)
        if notification:
            notification.is_read = True
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_all_as_read(self, user_id: UUID) -> int:
        notifications = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).all()
        
        count = len(notifications)
        for notification in notifications:
            notification.is_read = True
        
        self.db.commit()
        return count

    def get_unread_count(self, user_id: UUID) -> int:
        return self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()

    def delete_notification(self, notification_id: UUID) -> bool:
        notification = self.get_notification(notification_id)
        if notification:
            self.db.delete(notification)
            self.db.commit()
            return True
        return False
