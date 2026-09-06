"""WebSocket API endpoints with strict authentication and authorization."""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from uuid import UUID
from typing import Optional

from app.api.websocket import manager
from app.utils.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_WS_MESSAGE_SIZE = 64 * 1024  # 64KB max message


def _authenticate_websocket(token: Optional[str]) -> Optional[UUID]:
    """Validate JWT token and return user_id. Returns None if invalid."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            return UUID(payload["sub"])
    except Exception as e:
        logger.warning("WebSocket auth failed: %s", e, exc_info=True)
    return None


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, token: Optional[str] = None):
    user_id = _authenticate_websocket(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await manager.connect(websocket, user_id=user_id, room_id=room_id)
    logger.info("WebSocket connected: user=%s room=%s", user_id, room_id)

    try:
        while True:
            data = await websocket.receive_text()

            if len(data) > MAX_WS_MESSAGE_SIZE:
                await websocket.send_json({"type": "error", "message": "Message too large"})
                continue

            try:
                msg = json.loads(data)
                if msg.get("type") == "pong":
                    manager.handle_pong(websocket)
                    continue
            except (json.JSONDecodeError, AttributeError) as e:
                logger.debug("Malformed WebSocket message: %s", e)

            message = {"type": "message", "data": data, "room_id": room_id, "user_id": str(user_id)}
            await manager.broadcast_to_room(room_id, message)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s room=%s", user_id, room_id)
        manager.disconnect(websocket, user_id=user_id, room_id=room_id)
    except Exception as e:
        logger.error("WebSocket error in room endpoint: %s", e, exc_info=True)
        manager.disconnect(websocket, user_id=user_id, room_id=room_id)


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket, token: Optional[str] = None):
    user_id = _authenticate_websocket(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await manager.connect(websocket, user_id=user_id, room_id="ceo-dashboard")
    logger.info("WebSocket connected: user=%s room=%s", user_id, "ceo-dashboard")

    try:
        while True:
            data = await websocket.receive_text()

            if len(data) > MAX_WS_MESSAGE_SIZE:
                await websocket.send_json({"type": "error", "message": "Message too large"})
                continue

            try:
                msg = json.loads(data)
                if msg.get("type") == "pong":
                    manager.handle_pong(websocket)
                    continue
            except (json.JSONDecodeError, AttributeError) as e:
                logger.debug("Malformed WebSocket message: %s", e)

            message = {"type": "message", "data": data, "room_id": "ceo-dashboard", "user_id": str(user_id)}
            await manager.broadcast_to_room("ceo-dashboard", message)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s room=%s", user_id, "ceo-dashboard")
        manager.disconnect(websocket, user_id=user_id, room_id="ceo-dashboard")
    except Exception as e:
        logger.error("WebSocket error in dashboard endpoint: %s", e, exc_info=True)
        manager.disconnect(websocket, user_id=user_id, room_id="ceo-dashboard")


@router.websocket("/ws/user/{user_id_str}")
async def user_websocket(websocket: WebSocket, user_id_str: str, token: Optional[str] = None):
    """WebSocket endpoint for user-specific events. Token MUST match the user_id in the URL."""
    authenticated_user_id = _authenticate_websocket(token)
    if authenticated_user_id is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        requested_user_id = UUID(user_id_str)
    except ValueError:
        await websocket.close(code=4002, reason="Invalid user ID")
        return

    if authenticated_user_id != requested_user_id:
        await websocket.close(code=4003, reason="Cannot connect to another user's channel")
        return

    user_id = authenticated_user_id
    await manager.connect(websocket, user_id=user_id, room_id=f"user:{user_id}")
    logger.info("WebSocket connected: user=%s room=%s", user_id, f"user:{user_id}")

    try:
        while True:
            data = await websocket.receive_text()

            if len(data) > MAX_WS_MESSAGE_SIZE:
                await websocket.send_json({"type": "error", "message": "Message too large"})
                continue

            try:
                msg = json.loads(data)
                if msg.get("type") == "pong":
                    manager.handle_pong(websocket)
                    continue
            except (json.JSONDecodeError, AttributeError) as e:
                logger.debug("Malformed WebSocket message: %s", e)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s room=%s", user_id, f"user:{user_id}")
        manager.disconnect(websocket, user_id=user_id, room_id=f"user:{user_id}")
    except Exception as e:
        logger.error("WebSocket error in user endpoint: %s", e, exc_info=True)
        manager.disconnect(websocket, user_id=user_id, room_id=f"user:{user_id}")
