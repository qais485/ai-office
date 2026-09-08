"""Event handlers that bridge domain events to WebSocket delivery.

Every event is delivered only to the account that owns the data that raised
it (roles were removed — there is no global "ceo-dashboard" feed anymore).
Unresolvable ownership means the event is delivered to nobody (default-deny).
"""
import logging
from uuid import UUID
from app.events.types import DomainEvent, EventType
from app.events.bus import event_bus

logger = logging.getLogger(__name__)

# Will be set after ConnectionManager is initialized
_manager = None


def set_connection_manager(manager) -> None:
    global _manager
    _manager = manager


def get_manager():
    return _manager


async def _send_to_owner(message: dict, owner_id) -> None:
    """Deliver `message` to all of the owner's connections, or nobody."""
    if _manager is None or owner_id is None:
        return
    try:
        owner_uuid = owner_id if isinstance(owner_id, UUID) else UUID(str(owner_id))
    except (ValueError, TypeError):
        return
    await _manager.send_personal_message(message, owner_uuid)


async def _owner_from_agent(agent_id) -> UUID | None:
    """Resolve the owning account of an agent (strict)."""
    if not agent_id:
        return None
    try:
        from app.database.session import SessionLocal
        from app.models.agent import AIAgent

        db = SessionLocal()
        try:
            return db.query(AIAgent.user_id).filter(AIAgent.id == UUID(str(agent_id))).scalar()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"Could not resolve owner for agent {agent_id}: {e}")
        return None


async def _owner_from_account(account_id) -> UUID | None:
    """Resolve the owning account of an email/telegram/integration account."""
    if not account_id:
        return None
    try:
        from app.database.session import SessionLocal
        from app.models.email import EmailAccount
        from app.models.integration import IntegrationAccount

        db = SessionLocal()
        try:
            owner = db.query(EmailAccount.user_id).filter(
                EmailAccount.id == UUID(str(account_id))
            ).scalar()
            if owner is None:
                owner = db.query(IntegrationAccount.user_id).filter(
                    IntegrationAccount.id == UUID(str(account_id))
                ).scalar()
            return owner
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"Could not resolve owner for account {account_id}: {e}")
        return None


async def _owner_from_room(room_id) -> UUID | None:
    """Resolve the owning account of an office room."""
    if not room_id:
        return None
    try:
        from app.database.session import SessionLocal
        from app.models.room import OfficeRoom

        db = SessionLocal()
        try:
            return db.query(OfficeRoom.user_id).filter(OfficeRoom.id == UUID(str(room_id))).scalar()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"Could not resolve owner for room {room_id}: {e}")
        return None


async def _broadcast(event: DomainEvent) -> None:
    """Deliver an event to the owning account's WebSocket connections only."""
    if _manager is None:
        return

    message = event.to_dict()
    event_type = event.event_type
    data = event.data

    # Agent events → the agent's owner (plus its room, if any)
    if event_type in (
        EventType.AGENT_STATUS_CHANGED,
        EventType.AGENT_LIFECYCLE_CHANGED,
        EventType.AGENT_ERROR,
    ):
        room_id = data.get("room_id", "")
        if room_id:
            await _manager.broadcast_to_room(room_id, message)
        owner = await _owner_from_agent(data.get("agent_id") or data.get("agent"))
        await _send_to_owner(message, owner)

    # Task events → the owning agent's account
    elif event_type in (
        EventType.TASK_CREATED,
        EventType.TASK_UPDATED,
        EventType.TASK_COMPLETED,
        EventType.TASK_FAILED,
    ):
        owner = await _owner_from_agent(data.get("agent_id"))
        await _send_to_owner(message, owner)

    # Approval events → the owning agent's account
    elif event_type in (
        EventType.APPROVAL_CREATED,
        EventType.APPROVAL_APPROVED,
        EventType.APPROVAL_REJECTED,
    ):
        owner = await _owner_from_agent(data.get("agent_id"))
        await _send_to_owner(message, owner)

    # Notification events → the specific user (already owner-scoped)
    elif event_type == EventType.NOTIFICATION_CREATED:
        user_id = data.get("user_id", "")
        if user_id:
            try:
                await _manager.send_personal_message(message, UUID(str(user_id)))
            except (ValueError, KeyError):
                pass

    # Email events → the account's owner
    elif event_type == EventType.EMAIL_RECEIVED:
        owner = await _owner_from_account(data.get("account_id"))
        await _send_to_owner(message, owner)

    # Telegram account message events → the account's owner
    elif event_type == EventType.TELEGRAM_MESSAGE_RECEIVED:
        owner = await _owner_from_account(data.get("account_id"))
        await _send_to_owner(message, owner)

    # Telegram bot customer-chat events → the bot account's owner
    elif event_type == EventType.TELEGRAM_BOT_MESSAGE_RECEIVED:
        owner = await _owner_from_account(data.get("account_id"))
        await _send_to_owner(message, owner)

    # Room events → the room's owner
    elif event_type == EventType.ROOM_STATUS_CHANGED:
        room_id = data.get("room_id", "")
        if room_id:
            await _manager.broadcast_to_room(room_id, message)
        owner = await _owner_from_room(room_id)
        await _send_to_owner(message, owner)

    # Integration events → the integration account's owner
    elif event_type in (
        EventType.INTEGRATION_CONNECTED,
        EventType.INTEGRATION_DISCONNECTED,
        EventType.INTEGRATION_ERROR,
    ):
        owner = data.get("user_id") or await _owner_from_account(data.get("account_id"))
        await _send_to_owner(message, owner)

    # Tool execution events → the owning agent's account
    elif event_type in (
        EventType.TOOL_EXECUTION_STARTED,
        EventType.TOOL_EXECUTION_COMPLETED,
        EventType.TOOL_EXECUTION_FAILED,
    ):
        owner = await _owner_from_agent(data.get("agent_id"))
        await _send_to_owner(message, owner)

    # Activity events → the owning agent's account (plus its room, if any)
    elif event_type == EventType.ACTIVITY_LOGGED:
        room_id = data.get("room_id")
        if room_id:
            await _manager.broadcast_to_room(room_id, message)
        owner = await _owner_from_agent(data.get("agent_id"))
        await _send_to_owner(message, owner)

    # System alerts / knowledge updates → resolved per-owner when possible;
    # otherwise delivered to nobody (default-deny).
    elif event_type == EventType.SYSTEM_ALERT:
        owner = (
            data.get("user_id")
            or await _owner_from_agent(data.get("agent_id"))
            or await _owner_from_room(data.get("room_id"))
        )
        await _send_to_owner(message, owner)

    elif event_type == EventType.KNOWLEDGE_UPDATED:
        owner = data.get("user_id") or await _owner_from_agent(data.get("agent_id"))
        await _send_to_owner(message, owner)


def register_handlers() -> None:
    """Register all event handlers on the global event bus."""
    event_bus.subscribe_all(_broadcast)
    logger.info("Event handlers registered")
