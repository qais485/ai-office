from sqlalchemy import Column, String, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.models.base import BaseModel


class RoomStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class RoomVisualStatus(str, enum.Enum):
    OFFLINE = "offline"
    ONLINE_INACTIVE = "online_inactive"
    ONLINE_ACTIVE = "online_active"
    NEEDS_ATTENTION = "needs_attention"
    ERROR = "error"


class OfficeRoom(BaseModel):
    __tablename__ = "office_rooms"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(Enum(RoomStatus, values_callable=lambda obj: [e.value for e in obj]), default=RoomStatus.AVAILABLE, nullable=False)
    room_type = Column(String, nullable=True)
    capacity = Column(String, default="1")
    
    visual_status = Column(Enum(RoomVisualStatus, values_callable=lambda obj: [e.value for e in obj]), default=RoomVisualStatus.OFFLINE, nullable=False)
    current_agent_id = Column(String, nullable=True)
    current_user_id = Column(String, nullable=True)
    room_config = Column(JSON, nullable=True)
