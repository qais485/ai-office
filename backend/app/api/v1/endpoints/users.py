from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserResponse, UserRoleUpdate
from app.services.user_service import UserService
from app.api.deps import get_current_active_user, require_role

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO)),
):
    user_service = UserService(db)
    users = user_service.get_users()
    logger.debug("Listed %d users", len(users))
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO)),
):
    user_service = UserService(db)
    user = user_service.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    logger.debug("Retrieved user %s", user_id)
    return user


@router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: UUID,
    role_data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.CEO)),
):
    user_service = UserService(db)
    user = user_service.update_role(user_id, role_data.role)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    logger.info("Updated role for user %s to %s", user_id, role_data.role)
    return user
