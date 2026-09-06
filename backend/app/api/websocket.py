"""WebSocket connection manager with heartbeat, subscriptions, and cleanup."""
import json
import asyncio
import logging
from typing import Dict, Set, Optional, List
from uuid import UUID
from fastapi import WebSocket
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 10  # seconds


class ConnectionManager:
    """WebSocket connection manager for real-time updates.

    Supports:
    - Room-based subscriptions (agents in a room)
    - User-targeted messages (personal notifications)
    - CEO dashboard broadcasts
    - Heartbeat/ping-pong for connection health
    - Automatic cleanup of dead connections
    """

    def __init__(self):
        # room_id → set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # user_id → set of WebSocket connections
        self.user_connections: Dict[UUID, Set[WebSocket]] = {}
        # websocket → metadata dict
        self._connection_meta: Dict[WebSocket, dict] = {}
        # websocket → last pong time
        self._last_pong: Dict[WebSocket, float] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[UUID] = None,
        room_id: Optional[str] = None,
    ) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()

        meta = {
            "user_id": user_id,
            "room_id": room_id,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }
        self._connection_meta[websocket] = meta
        self._last_pong[websocket] = datetime.now(timezone.utc).timestamp()

        if room_id:
            if room_id not in self.active_connections:
                self.active_connections[room_id] = set()
            self.active_connections[room_id].add(websocket)

        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)

        logger.info(
            f"WebSocket connected: room={room_id}, user={user_id}, "
            f"total rooms={len(self.active_connections)}, "
            f"total users={len(self.user_connections)}"
        )

        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "room_id": room_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def disconnect(
        self,
        websocket: WebSocket,
        user_id: Optional[UUID] = None,
        room_id: Optional[str] = None,
    ) -> None:
        """Remove a WebSocket connection."""
        if room_id and room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        self._connection_meta.pop(websocket, None)
        self._last_pong.pop(websocket, None)

        logger.info(
            f"WebSocket disconnected: room={room_id}, user={user_id}"
        )

    def handle_pong(self, websocket: WebSocket) -> None:
        """Record a pong response from a client."""
        self._last_pong[websocket] = datetime.now(timezone.utc).timestamp()

    async def send_personal_message(self, message: dict, user_id: UUID) -> None:
        """Send a message to all connections for a specific user."""
        if user_id in self.user_connections:
            dead = []
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead.append(connection)
            for ws in dead:
                self.user_connections[user_id].discard(ws)

    async def broadcast_to_room(self, room_id: str, message: dict) -> None:
        """Broadcast a message to all connections in a room."""
        if room_id in self.active_connections:
            dead = []
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead.append(connection)
            for ws in dead:
                self.active_connections[room_id].discard(ws)

    async def broadcast_approval_request(
        self,
        approval_id: UUID,
        agent_id: UUID,
        room_id: str,
        reason: str,
    ) -> None:
        """Broadcast an approval request to the dashboard room."""
        message = {
            "type": "approval_request",
            "approval_id": str(approval_id),
            "agent_id": str(agent_id),
            "room_id": room_id,
            "reason": reason,
        }
        await self.broadcast_to_room("dashboard", message)

    async def broadcast_agent_status_change(
        self,
        agent_id: UUID,
        room_id: str,
        new_status: str,
        old_status: str,
    ) -> None:
        """Broadcast an agent visual status change to the dashboard room."""
        message = {
            "type": "agent_status_changed",
            "agent_id": str(agent_id),
            "room_id": room_id,
            "new_status": new_status,
            "old_status": old_status,
        }
        await self.broadcast_to_room("dashboard", message)

    async def broadcast_all(self, message: dict) -> None:
        """Broadcast a message to all connected clients."""
        all_connections: Set[WebSocket] = set()
        for conns in self.active_connections.values():
            all_connections.update(conns)
        for conns in self.user_connections.values():
            all_connections.update(conns)

        dead = []
        for connection in all_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for ws in dead:
            self._cleanup_dead(ws)

    def _cleanup_dead(self, websocket: WebSocket) -> None:
        """Remove a dead connection from all tracking structures."""
        meta = self._connection_meta.pop(websocket, {})
        user_id = meta.get("user_id")
        room_id = meta.get("room_id")

        if room_id and room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        self._last_pong.pop(websocket, None)

    async def start_heartbeat(self) -> None:
        """Start the background heartbeat task."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat task."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        """Send periodic pings and clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                now = datetime.now(timezone.utc).timestamp()
                stale = []

                all_connections: Set[WebSocket] = set()
                for conns in self.active_connections.values():
                    all_connections.update(conns)
                for conns in self.user_connections.values():
                    all_connections.update(conns)

                for ws in all_connections:
                    last = self._last_pong.get(ws, 0)
                    if now - last > HEARTBEAT_INTERVAL + HEARTBEAT_TIMEOUT:
                        stale.append(ws)
                    else:
                        try:
                            asyncio.ensure_future(ws.send_json({"type": "ping"}))
                        except Exception:
                            stale.append(ws)

                for ws in stale:
                    self._cleanup_dead(ws)
                    try:
                        await ws.close(code=1000, reason="heartbeat timeout")
                    except Exception:
                        pass

                if stale:
                    logger.info(f"Cleaned up {len(stale)} stale WebSocket connections")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(HEARTBEAT_INTERVAL)

    @property
    def connection_count(self) -> int:
        """Total number of active connections."""
        count = set()
        for conns in self.active_connections.values():
            count.update(conns)
        for conns in self.user_connections.values():
            count.update(conns)
        return len(count)

    def get_room_connections(self, room_id: str) -> int:
        return len(self.active_connections.get(room_id, set()))

    def get_user_connections(self, user_id: UUID) -> int:
        return len(self.user_connections.get(user_id, set()))


# Global singleton
manager = ConnectionManager()
