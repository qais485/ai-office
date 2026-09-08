"""Domain event types and payload definitions."""
import enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID


class EventType(str, enum.Enum):
    # Agent events
    AGENT_STATUS_CHANGED = "agent_status_changed"
    AGENT_LIFECYCLE_CHANGED = "agent_lifecycle_changed"
    AGENT_ERROR = "agent_error"

    # Task events
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Approval events
    APPROVAL_CREATED = "approval_created"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"

    # Notification events
    NOTIFICATION_CREATED = "notification_created"

    # Email events
    EMAIL_RECEIVED = "email_received"

    # Telegram (MTProto account) events
    TELEGRAM_MESSAGE_RECEIVED = "telegram_message_received"

    # Telegram Bot events
    TELEGRAM_BOT_MESSAGE_RECEIVED = "telegram_bot_message_received"

    # Room events
    ROOM_STATUS_CHANGED = "room_status_changed"

    # Integration events
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_DISCONNECTED = "integration_disconnected"
    INTEGRATION_ERROR = "integration_error"

    # Tool execution events
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"

    # Activity events
    ACTIVITY_LOGGED = "activity_logged"

    # Knowledge events
    KNOWLEDGE_UPDATED = "knowledge_updated"

    # System events
    SYSTEM_ALERT = "system_alert"


@dataclass
class DomainEvent:
    """Base class for all domain events."""
    event_type: EventType
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type.value,
            "timestamp": self.timestamp,
            **self.data,
        }


@dataclass
class AgentStatusEvent(DomainEvent):
    event_type: EventType = EventType.AGENT_STATUS_CHANGED
    agent_id: str = ""
    room_id: str = ""
    status: str = ""
    old_status: str = ""

    def __post_init__(self):
        self.data = {
            "agent_id": self.agent_id,
            "room_id": self.room_id,
            "status": self.status,
            "old_status": self.old_status,
        }


@dataclass
class AgentLifecycleEvent(DomainEvent):
    event_type: EventType = EventType.AGENT_LIFECYCLE_CHANGED
    agent_id: str = ""
    lifecycle_status: str = ""
    old_lifecycle_status: str = ""

    def __post_init__(self):
        self.data = {
            "agent_id": self.agent_id,
            "lifecycle_status": self.lifecycle_status,
            "old_lifecycle_status": self.old_lifecycle_status,
        }


@dataclass
class AgentErrorEvent(DomainEvent):
    event_type: EventType = EventType.AGENT_ERROR
    agent_id: str = ""
    room_id: str = ""
    error_message: str = ""
    task_id: str = ""

    def __post_init__(self):
        self.data = {
            "agent_id": self.agent_id,
            "room_id": self.room_id,
            "error_message": self.error_message,
            "task_id": self.task_id,
        }


@dataclass
class TaskEvent(DomainEvent):
    event_type: EventType = EventType.TASK_CREATED
    task_id: str = ""
    agent_id: str = ""
    title: str = ""
    status: str = ""
    old_status: str = ""
    priority: str = ""
    # True for internal runtime bookkeeping tasks (trigger execution tracking).
    # These must NOT re-fire agent triggers (infinite loop prevention).
    is_execution_bookkeeping: bool = False

    def __post_init__(self):
        self.data = {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "title": self.title,
            "status": self.status,
            "old_status": self.old_status,
            "priority": self.priority,
            "is_execution_bookkeeping": self.is_execution_bookkeeping,
        }


@dataclass
class ApprovalEvent(DomainEvent):
    event_type: EventType = EventType.APPROVAL_CREATED
    approval_id: str = ""
    agent_id: str = ""
    action: str = ""
    risk_level: str = ""
    status: str = ""
    old_status: str = ""
    task_title: str = ""

    def __post_init__(self):
        self.data = {
            "approval_id": self.approval_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "risk_level": self.risk_level,
            "status": self.status,
            "old_status": self.old_status,
            "task_title": self.task_title,
        }


@dataclass
class NotificationEvent(DomainEvent):
    event_type: EventType = EventType.NOTIFICATION_CREATED
    notification_id: str = ""
    user_id: str = ""
    notification_type: str = ""
    title: str = ""
    message: str = ""
    priority: str = ""

    def __post_init__(self):
        self.data = {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "notification_type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "priority": self.priority,
        }


@dataclass
class EmailEvent(DomainEvent):
    event_type: EventType = EventType.EMAIL_RECEIVED
    email_id: str = ""
    from_address: str = ""
    subject: str = ""
    account_id: str = ""

    def __post_init__(self):
        self.data = {
            "email_id": self.email_id,
            "from_address": self.from_address,
            "subject": self.subject,
            "account_id": self.account_id,
        }


@dataclass
class TelegramMessageEvent(DomainEvent):
    event_type: EventType = EventType.TELEGRAM_MESSAGE_RECEIVED
    message_id: str = ""
    chat_id: str = ""
    chat_title: str = ""
    sender_id: str = ""
    text: str = ""
    account_id: str = ""

    def __post_init__(self):
        self.data = {
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "chat_title": self.chat_title,
            "sender_id": self.sender_id,
            "text": self.text,
            "account_id": self.account_id,
        }


@dataclass
class TelegramBotMessageEvent(DomainEvent):
    event_type: EventType = EventType.TELEGRAM_BOT_MESSAGE_RECEIVED
    message_id: str = ""
    chat_id: str = ""
    chat_title: str = ""
    sender_id: str = ""
    text: str = ""
    account_id: str = ""

    def __post_init__(self):
        self.data = {
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "chat_title": self.chat_title,
            "sender_id": self.sender_id,
            "text": self.text,
            "account_id": self.account_id,
        }


@dataclass
class RoomStatusEvent(DomainEvent):
    event_type: EventType = EventType.ROOM_STATUS_CHANGED
    room_id: str = ""
    status: str = ""
    old_status: str = ""
    agent_id: str = ""

    def __post_init__(self):
        self.data = {
            "room_id": self.room_id,
            "status": self.status,
            "old_status": self.old_status,
            "agent_id": self.agent_id,
        }


@dataclass
class IntegrationEvent(DomainEvent):
    event_type: EventType = EventType.INTEGRATION_CONNECTED
    integration_id: str = ""
    account_id: str = ""
    integration_name: str = ""
    user_id: str = ""

    def __post_init__(self):
        self.data = {
            "integration_id": self.integration_id,
            "account_id": self.account_id,
            "integration_name": self.integration_name,
            "user_id": self.user_id,
        }


@dataclass
class ToolExecutionEvent(DomainEvent):
    event_type: EventType = EventType.TOOL_EXECUTION_STARTED
    approval_id: str = ""
    agent_id: str = ""
    tool_name: str = ""
    action: str = ""
    status: str = ""
    error_message: str = ""

    def __post_init__(self):
        self.data = {
            "approval_id": self.approval_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "action": self.action,
            "status": self.status,
            "error_message": self.error_message,
        }


@dataclass
class ActivityEvent(DomainEvent):
    event_type: EventType = EventType.ACTIVITY_LOGGED
    activity_id: str = ""
    agent_id: str = ""
    room_id: str = ""
    activity_type: str = ""
    description: str = ""
    status: str = ""
    created_at: str = ""

    def __post_init__(self):
        self.data = {
            "activity_id": self.activity_id,
            "agent_id": self.agent_id,
            "room_id": self.room_id,
            "activity_type": self.activity_type,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
        }
