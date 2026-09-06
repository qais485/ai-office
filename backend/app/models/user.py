from sqlalchemy import Column, String, Enum, Boolean
import enum

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    CEO = "ceo"
    ADMIN = "admin"
    USER = "user"


class User(BaseModel):
    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    google_id = Column(String, unique=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    role = Column(Enum(UserRole, values_callable=lambda obj: [e.value for e in obj]), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
