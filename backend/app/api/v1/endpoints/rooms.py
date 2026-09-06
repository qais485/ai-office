from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.room import RoomCreate, RoomUpdate, RoomResponse
from app.services.room_service import RoomService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[RoomResponse])
def get_rooms(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    rooms = room_service.get_rooms(user_id=current_user.id)
    logger.debug("Listed %d rooms for user %s", len(rooms), current_user.id)
    return rooms


@router.get("/statuses")
def get_room_statuses(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    return room_service.get_all_room_statuses(user_id=current_user.id)


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(room_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    room = room_service.get_room(room_id, user_id=current_user.id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    logger.debug("Retrieved room %s for user %s", room_id, current_user.id)
    return room


@router.get("/{room_id}/status")
def get_room_status(room_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    # Verify ownership first
    room = room_service.get_room(room_id, user_id=current_user.id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    status = room_service.get_room_visual_status(room_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.post("/", response_model=RoomResponse)
def create_room(room: RoomCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    created = room_service.create_room(room, user_id=current_user.id)
    logger.info("Created room %s for user %s", created.id, current_user.id)
    return created


@router.put("/{room_id}", response_model=RoomResponse)
def update_room(room_id: UUID, room: RoomUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    updated = room_service.update_room(room_id, room, user_id=current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Room not found")
    logger.info("Updated room %s for user %s", room_id, current_user.id)
    return updated


@router.delete("/{room_id}")
def delete_room(room_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    deleted = room_service.delete_room(room_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Room not found")
    logger.info("Deleted room %s for user %s", room_id, current_user.id)
    return {"detail": "Room deleted"}


@router.post("/{room_id}/enter")
def enter_room(room_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    result = room_service.enter_room(room_id, current_user.id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    logger.info("User %s entered room %s", current_user.id, room_id)
    return result


@router.post("/{room_id}/leave")
def leave_room(room_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    result = room_service.leave_room(room_id, current_user.id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    logger.info("User %s left room %s", current_user.id, room_id)
    return result


@router.post("/sync-statuses")
def sync_room_statuses(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    room_service = RoomService(db)
    count = room_service.sync_all_room_statuses()
    logger.info("Synced %d room statuses", count)
    return {"synced": count}
