from sqlalchemy import Column, String, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel


class Permission(BaseModel):
    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("name", name="uq_permission_name"),
    )

    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)
    risk_level = Column(String(20), default="low", nullable=False)
    default_status = Column(String(20), default="allowed", nullable=False)  # allowed, approval_required, denied
    default_approval_required = Column(Boolean, default=False, nullable=False)  # Kept for backwards compatibility
    is_active = Column(Boolean, default=True, nullable=False)
