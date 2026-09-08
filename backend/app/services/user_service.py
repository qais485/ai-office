from typing import List, Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.user import User, USER_ROLE
from app.schemas.user import UserUpdate
import logging

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_users(self) -> List[User]:
        return self.db.query(User).all()

    def get_user(self, user_id: UUID) -> Optional[User]:
        user = self.db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None
        # Legacy databases may still carry 'ceo'/'admin' role strings; roles
        # no longer exist, so normalize on read (no privileges attached).
        if user.role != USER_ROLE:
            user.role = USER_ROLE
            self.db.commit()
        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.google_id == google_id).first()

    def get_or_create_google_user(
        self,
        google_id: str,
        email: str,
        name: str,
        avatar_url: Optional[str] = None,
    ) -> User:
        logger.debug("Getting or creating Google user: google_id=%s email=%s", google_id, email)
        user = self.get_user_by_google_id(google_id)
        if user:
            user.email = email
            user.name = name
            if avatar_url:
                user.avatar_url = avatar_url
            if user.role != USER_ROLE:
                user.role = USER_ROLE
            self.db.commit()
            self.db.refresh(user)
            return user

        user = self.get_user_by_email(email)
        if user:
            user.google_id = google_id
            if avatar_url:
                user.avatar_url = avatar_url
            if user.role != USER_ROLE:
                user.role = USER_ROLE
            self.db.commit()
            self.db.refresh(user)
            return user

        user = User(
            email=email,
            name=name,
            google_id=google_id,
            avatar_url=avatar_url,
            role=USER_ROLE,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info("New user created: id=%s email=%s role=%s", user.id, user.email, user.role)
        return user

    def update_user(self, user_id: UUID, user_data: UserUpdate) -> Optional[User]:
        user = self.get_user(user_id)
        if user:
            update_data = user_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(user, key, value)
            self.db.commit()
            self.db.refresh(user)
        return user

    def delete_user(self, user_id: UUID) -> bool:
        user = self.get_user(user_id)
        if user:
            self.db.delete(user)
            self.db.commit()
            return True
        return False
