"""Convenience functions for publishing domain events from services.

Services import these functions to publish events without depending on
the WebSocket implementation directly.
"""
import logging
from typing import Optional
from uuid import UUID

from app.events.bus import event_bus
from app.events.types import (
    EventType, DomainEvent, AgentStatusEvent, AgentLifecycleEvent,
    AgentErrorEvent, TaskEvent, ApprovalEvent, NotificationEvent,
    EmailEvent, RoomStatusEvent, IntegrationEvent, ToolExecutionEvent,
    ActivityEvent,
)

logger = logging.getLogger(__name__)


async def publish_agent_status_changed(
    agent_id: UUID, room_id: str, status: str, old_status: str
) -> None:
    event = AgentStatusEvent(
        agent_id=str(agent_id),
        room_id=room_id,
        status=status,
        old_status=old_status,
    )
    await event_bus.publish(event)


async def publish_agent_lifecycle_changed(
    agent_id: UUID, lifecycle_status: str, old_lifecycle_status: str
) -> None:
    event = AgentLifecycleEvent(
        agent_id=str(agent_id),
        lifecycle_status=lifecycle_status,
        old_lifecycle_status=old_lifecycle_status,
    )
    await event_bus.publish(event)


async def publish_agent_error(
    agent_id: UUID, room_id: str, error_message: str, task_id: UUID = None
) -> None:
    event = AgentErrorEvent(
        agent_id=str(agent_id),
        room_id=room_id,
        error_message=error_message,
        task_id=str(task_id) if task_id else "",
    )
    await event_bus.publish(event)


async def publish_task_event(
    event_type: EventType,
    task_id: UUID,
    agent_id: UUID,
    title: str,
    status: str,
    old_status: str = "",
    priority: str = "",
    is_execution_bookkeeping: bool = False,
) -> None:
    event = TaskEvent(
        event_type=event_type,
        task_id=str(task_id),
        agent_id=str(agent_id),
        title=title,
        status=status,
        old_status=old_status,
        priority=priority,
        is_execution_bookkeeping=is_execution_bookkeeping,
    )
    await event_bus.publish(event)


async def publish_approval_event(
    event_type: EventType,
    approval_id: UUID,
    agent_id: UUID,
    action: str,
    risk_level: str,
    status: str,
    old_status: str = "",
    task_title: str = "",
) -> None:
    event = ApprovalEvent(
        event_type=event_type,
        approval_id=str(approval_id),
        agent_id=str(agent_id),
        action=action,
        risk_level=risk_level,
        status=status,
        old_status=old_status,
        task_title=task_title,
    )
    await event_bus.publish(event)


async def publish_notification_created(
    notification_id: UUID,
    user_id: UUID,
    notification_type: str,
    title: str,
    message: str,
    priority: str = "low",
) -> None:
    event = NotificationEvent(
        notification_id=str(notification_id),
        user_id=str(user_id),
        notification_type=notification_type,
        title=title,
        message=message or "",
        priority=priority,
    )
    await event_bus.publish(event)


async def publish_email_received(
    email_id: UUID, from_address: str, subject: str, account_id: UUID = None
) -> None:
    event = EmailEvent(
        email_id=str(email_id),
        from_address=from_address,
        subject=subject,
        account_id=str(account_id) if account_id else "",
    )
    await event_bus.publish(event)


async def publish_room_status_changed(
    room_id: UUID, status: str, old_status: str, agent_id: UUID = None
) -> None:
    event = RoomStatusEvent(
        room_id=str(room_id),
        status=status,
        old_status=old_status,
        agent_id=str(agent_id) if agent_id else "",
    )
    await event_bus.publish(event)


async def publish_integration_event(
    event_type: EventType,
    integration_id: UUID,
    account_id: UUID,
    integration_name: str,
    user_id: UUID,
) -> None:
    event = IntegrationEvent(
        event_type=event_type,
        integration_id=str(integration_id),
        account_id=str(account_id),
        integration_name=integration_name,
        user_id=str(user_id),
    )
    await event_bus.publish(event)


async def publish_tool_execution_event(
    event_type: EventType,
    approval_id: Optional[UUID],
    agent_id: UUID,
    tool_name: str,
    action: str,
    status: str = "",
    error_message: str = "",
) -> None:
    event = ToolExecutionEvent(
        event_type=event_type,
        approval_id=str(approval_id) if approval_id else "",
        agent_id=str(agent_id),
        tool_name=tool_name,
        action=action,
        status=status,
        error_message=error_message,
    )
    await event_bus.publish(event)


async def publish_activity_logged(
    activity_id: UUID,
    agent_id: UUID,
    room_id: Optional[UUID],
    activity_type: str,
    description: str,
    status: str = "",
    created_at: Optional[str] = None,
) -> None:
    """Broadcast a newly persisted AgentActivity so dashboards update live."""
    event = ActivityEvent(
        activity_id=str(activity_id),
        agent_id=str(agent_id),
        room_id=str(room_id) if room_id else "",
        activity_type=activity_type,
        description=description or "",
        status=status or "",
        created_at=created_at or "",
    )
    await event_bus.publish(event)
