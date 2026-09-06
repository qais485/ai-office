"""Event handlers that bridge domain events to WebSocket broadcasts.

These handlers are registered on the event bus and forward events
to connected WebSocket clients via the ConnectionManager.
"""
import logging
from typing import Set
from app.events.types import DomainEvent, EventType
from app.events.bus import event_bus

logger = logging.getLogger(__name__)

# Will be set after ConnectionManager is initialized
_manager = None
# Track which user IDs are interested in CEO dashboard updates
_ceo_dashboard_users: Set[str] = set()


def set_connection_manager(manager) -> None:
    global _manager
    _manager = manager


def get_manager():
    return _manager


async def _broadcast(event: DomainEvent) -> None:
    """Broadcast an event to appropriate WebSocket connections."""
    if _manager is None:
        return

    message = event.to_dict()

    event_type = event.event_type

    # Agent events → broadcast to room
    if event_type in (
        EventType.AGENT_STATUS_CHANGED,
        EventType.AGENT_LIFECYCLE_CHANGED,
        EventType.AGENT_ERROR,
    ):
        room_id = event.data.get("room_id", "")
        if room_id:
            await _manager.broadcast_to_room(room_id, message)
        # Also broadcast to CEO dashboard
        await _manager.broadcast_to_room("ceo-dashboard", message)

    # Task events → broadcast to room + CEO dashboard
    elif event_type in (
        EventType.TASK_CREATED,
        EventType.TASK_UPDATED,
        EventType.TASK_COMPLETED,
        EventType.TASK_FAILED,
    ):
        agent_id = event.data.get("agent_id", "")
        # Find agent's room and broadcast there
        room_id = await _get_agent_room(agent_id)
        if room_id:
            await _manager.broadcast_to_room(room_id, message)
        await _manager.broadcast_to_room("ceo-dashboard", message)

    # Approval events → broadcast to room + CEO dashboard
    elif event_type in (
        EventType.APPROVAL_CREATED,
        EventType.APPROVAL_APPROVED,
        EventType.APPROVAL_REJECTED,
    ):
        agent_id = event.data.get("agent_id", "")
        room_id = await _get_agent_room(agent_id)
        if room_id:
            await _manager.broadcast_to_room(room_id, message)
        await _manager.broadcast_to_room("ceo-dashboard", message)

    # Notification events → send to specific user
    elif event_type == EventType.NOTIFICATION_CREATED:
        user_id = event.data.get("user_id", "")
        if user_id:
            from uuid import UUID
            try:
                await _manager.send_personal_message(message, UUID(user_id))
            except (ValueError, KeyError):
                pass

    # Email events → CEO dashboard
    elif event_type == EventType.EMAIL_RECEIVED:
        await _manager.broadcast_to_room("ceo-dashboard", message)

    # Room events → broadcast to room + CEO dashboard
    elif event_type == EventType.ROOM_STATUS_CHANGED:
        room_id = event.data.get("room_id", "")
        if room_id:
            await _manager.broadcast_to_room(room_id, message)
        await _manager.broadcast_to_room("ceo-dashboard", message)

    # Integration events → broadcast to user + CEO dashboard
    elif event_type in (
        EventType.INTEGRATION_CONNECTED,
        EventType.INTEGRATION_DISCONNECTED,
        EventType.INTEGRATION_ERROR,
    ):
        user_id = event.data.get("user_id", "")
        if user_id:
            from uuid import UUID
            try:
                await _manager.send_personal_message(message, UUID(user_id))
            except (ValueError, KeyError):
                pass
        await _manager.broadcast_to_room("ceo-dashboard", message)

    # Tool execution events → broadcast to room + CEO dashboard
    elif event_type in (
        EventType.TOOL_EXECUTION_STARTED,
        EventType.TOOL_EXECUTION_COMPLETED,
        EventType.TOOL_EXECUTION_FAILED,
    ):
        agent_id = event.data.get("agent_id", "")
        room_id = await _get_agent_room(agent_id)
        if room_id:
            await _manager.broadcast_to_room(room_id, message)
        await _manager.broadcast_to_room("ceo-dashboard", message)

    # Activity events → broadcast to the agent's room + CEO dashboard so
    # every dashboard tab (Overview/Tasks/Activity/...) updates live.
    elif event_type == EventType.ACTIVITY_LOGGED:
        room_id = event.data.get("room_id") or await _get_agent_room(event.data.get("agent_id", ""))
        if room_id:
            await _manager.broadcast_to_room(room_id, message)
        await _manager.broadcast_to_room("ceo-dashboard", message)

    # System alerts → CEO dashboard
    elif event_type == EventType.SYSTEM_ALERT:
        await _manager.broadcast_to_room("ceo-dashboard", message)

    # Knowledge events → CEO dashboard
    elif event_type == EventType.KNOWLEDGE_UPDATED:
        await _manager.broadcast_to_room("ceo-dashboard", message)


async def _get_agent_room(agent_id: str) -> str:
    """Look up the room for an agent from the database."""
    if not agent_id:
        return ""
    try:
        from uuid import UUID
        from app.database.session import SessionLocal
        from app.models.agent import AIAgent

        db = SessionLocal()
        try:
            agent = db.query(AIAgent.room_id).filter(
                AIAgent.id == UUID(agent_id)
            ).first()
            return str(agent.room_id) if agent and agent.room_id else ""
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"Could not resolve room for agent {agent_id}: {e}")
        return ""


def register_handlers() -> None:
    """Register all event handlers on the global event bus."""
    event_bus.subscribe_all(_broadcast)
    logger.info("Event handlers registered")
