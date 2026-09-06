from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class RoomBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "available"
    room_type: Optional[str] = None
    capacity: str = "1"


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    room_type: Optional[str] = None
    capacity: Optional[str] = None
    visual_status: Optional[str] = None
    room_config: Optional[dict] = None


class RoomResponse(RoomBase):
    id: UUID
    visual_status: Optional[str] = None
    current_agent_id: Optional[str] = None
    current_user_id: Optional[str] = None
    room_config: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
