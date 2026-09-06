from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.user import UserRole


class GoogleTokenRequest(BaseModel):
    credential: str


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    is_active: bool
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserMeResponse(UserResponse):
    pass


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
