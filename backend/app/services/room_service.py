import asyncio
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

from app.models.room import OfficeRoom, RoomStatus, RoomVisualStatus
from app.models.agent import AIAgent, LifecycleStatus
from app.models.task import Task, TaskStatus
from app.models.approval import Approval
from app.schemas.room import RoomCreate, RoomUpdate
from app.api.websocket import manager
import logging

logger = logging.getLogger(__name__)


class RoomService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_rooms(self, user_id: Optional[UUID] = None) -> List[OfficeRoom]:
        query = self.db.query(OfficeRoom)
        if user_id is not None:
            query = query.filter(OfficeRoom.user_id == user_id)
        return query.all()
    
    def get_room(self, room_id: UUID, user_id: Optional[UUID] = None) -> Optional[OfficeRoom]:
        query = self.db.query(OfficeRoom).filter(OfficeRoom.id == room_id)
        if user_id is not None:
            query = query.filter(OfficeRoom.user_id == user_id)
        return query.first()
    
    def create_room(self, room_data: RoomCreate, user_id: Optional[UUID] = None) -> OfficeRoom:
        logger.info("Creating room: %s", room_data.name if hasattr(room_data, 'name') else 'new')
        room = OfficeRoom(**room_data.model_dump(), user_id=user_id)
        self.db.add(room)
        self.db.commit()
        self.db.refresh(room)
        logger.info("Room created: id=%s", room.id)
        return room
    
    def update_room(self, room_id: UUID, room_data: RoomUpdate, user_id: Optional[UUID] = None) -> Optional[OfficeRoom]:
        room = self.get_room(room_id, user_id=user_id)
        if room:
            update_data = room_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(room, key, value)
            self.db.commit()
            self.db.refresh(room)
        return room
    
    def delete_room(self, room_id: UUID, user_id: Optional[UUID] = None) -> bool:
        room = self.get_room(room_id, user_id=user_id)
        if room:
            # Unassign all agents from this room before deleting
            self.db.query(AIAgent).filter(AIAgent.room_id == room_id).update({AIAgent.room_id: None})
            self.db.delete(room)
            self.db.commit()
            return True
        return False
    
    def get_room_visual_status(self, room_id: UUID) -> Dict[str, Any]:
        room = self.get_room(room_id)
        if not room:
            return {"error": "Room not found"}
        
        agent = None
        if room.current_agent_id:
            agent = self.db.query(AIAgent).filter(AIAgent.id == room.current_agent_id).first()
        
        has_pending_approvals = False
        task_count = 0
        
        if agent:
            has_pending_approvals = self.db.query(Approval).filter(
                Approval.agent_id == agent.id,
                Approval.status == "pending"
            ).count() > 0
            
            task_count = self.db.query(Task).filter(
                Task.agent_id == agent.id,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
            ).count()
        
        return {
            "room_id": str(room.id),
            "name": room.name,
            "visual_status": room.visual_status.value if room.visual_status else RoomVisualStatus.OFFLINE.value,
            "agent_name": agent.name if agent else None,
            "agent_status": agent.status if agent else None,
            "has_pending_approvals": has_pending_approvals,
            "task_count": task_count
        }
    
    def get_all_room_statuses(self, user_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        rooms = self.get_rooms(user_id=user_id)
        statuses = []
        for room in rooms:
            status = self.get_room_visual_status(room.id)
            statuses.append(status)
        return statuses
    
    def update_room_visual_status(self, room_id: UUID, visual_status: RoomVisualStatus) -> Optional[OfficeRoom]:
        room = self.get_room(room_id)
        if room:
            room.visual_status = visual_status
            self.db.commit()
            self.db.refresh(room)
        return room
    
    def enter_room(self, room_id: UUID, user_id: UUID) -> Dict[str, Any]:
        room = self.get_room(room_id)
        if not room:
            return {"success": False, "error": "Room not found"}
        
        # Check room ownership if user_id is set
        if room.user_id and room.user_id != user_id:
            return {"success": False, "error": "Room not found"}
        
        if room.current_user_id and room.current_user_id != str(user_id):
            return {"success": False, "error": "Room is occupied by another user"}
        
        room.current_user_id = str(user_id)
        room.status = RoomStatus.OCCUPIED
        self.db.commit()
        
        agent = None
        if room.current_agent_id:
            agent = self.db.query(AIAgent).filter(AIAgent.id == room.current_agent_id).first()
            # If agent was deleted but room still references it, clear the reference
            if not agent:
                room.current_agent_id = None
                self.db.commit()
        
        return {
            "success": True,
            "room": {
                "id": str(room.id),
                "name": room.name,
                "visual_status": room.visual_status.value if room.visual_status else None
            },
            "agent": {
                "id": str(agent.id),
                "name": agent.name,
                "role": agent.role,
                "status": agent.status,
                "lifecycle_status": agent.lifecycle_status.value if agent.lifecycle_status else None
            } if agent else None
        }
    
    def leave_room(self, room_id: UUID, user_id: UUID) -> Dict[str, Any]:
        room = self.get_room(room_id)
        if not room:
            return {"success": False, "error": "Room not found"}
        
        if room.current_user_id != str(user_id):
            return {"success": False, "error": "You are not in this room"}
        
        room.current_user_id = None
        room.status = RoomStatus.AVAILABLE
        self.db.commit()
        
        return {
            "success": True,
            "message": "Left room successfully"
        }
    
    def sync_room_status_from_agent(self, room_id: UUID) -> Optional[OfficeRoom]:
        room = self.get_room(room_id)
        if not room or not room.current_agent_id:
            return room
        
        agent = self.db.query(AIAgent).filter(AIAgent.id == room.current_agent_id).first()
        if not agent:
            return room
        
        old_status = room.visual_status
        
        if agent.lifecycle_status == LifecycleStatus.ERROR:
            room.visual_status = RoomVisualStatus.ERROR
        elif agent.lifecycle_status == LifecycleStatus.ACTIVE:
            if agent.status == "active":
                room.visual_status = RoomVisualStatus.ONLINE_ACTIVE
            else:
                room.visual_status = RoomVisualStatus.ONLINE_INACTIVE
        elif agent.lifecycle_status == LifecycleStatus.PAUSED:
            room.visual_status = RoomVisualStatus.ONLINE_INACTIVE
        elif agent.lifecycle_status == LifecycleStatus.DISABLED:
            room.visual_status = RoomVisualStatus.OFFLINE
        else:
            room.visual_status = RoomVisualStatus.OFFLINE
        
        has_pending = self.db.query(Approval).filter(
            Approval.agent_id == agent.id,
            Approval.status == "pending"
        ).count() > 0
        
        if has_pending:
            room.visual_status = RoomVisualStatus.NEEDS_ATTENTION
        
        self.db.commit()
        self.db.refresh(room)
        
        if old_status != room.visual_status:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        manager.broadcast_agent_status_change(
                            agent.id,
                            str(room.id),
                            room.visual_status.value,
                            old_status.value if old_status else "unknown"
                        )
                    )
            except Exception:
                logger.warning("Failed to broadcast room status change", exc_info=True)
        
        return room
    
    def sync_all_room_statuses(self) -> int:
        rooms = self.db.query(OfficeRoom).filter(OfficeRoom.current_agent_id.isnot(None)).all()
        count = 0
        for room in rooms:
            self.sync_room_status_from_agent(room.id)
            count += 1
        return count
