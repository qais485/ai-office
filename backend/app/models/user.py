from sqlalchemy import Column, String, Boolean

from app.models.base import BaseModel


# Roles removed: every account is a plain user scoped strictly to its own
# data. The legacy 'ceo'/'admin' values may still exist in old databases;
# UserService normalizes them to "user" on load.
USER_ROLE = "user"


class User(BaseModel):
    __tablename__ = "users"
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    google_id = Column(String, unique=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    role = Column(String(20), default=USER_ROLE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
