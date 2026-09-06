"""Tests for the WebSocket event system (event bus, types, handlers, publisher)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.events.types import EventType, DomainEvent, AgentStatusEvent, TaskEvent, ApprovalEvent
from app.events.bus import EventBus, event_bus
from app.events.publisher import (
    publish_agent_status_changed,
    publish_task_event,
    publish_approval_event,
    publish_notification_created,
    publish_integration_event,
    publish_tool_execution_event,
)


@pytest.fixture
def fresh_event_bus():
    """Create a fresh EventBus for isolated tests."""
    return EventBus()


@pytest.fixture
def mock_handler():
    return AsyncMock()


class TestEventType:
    def test_agent_events_exist(self):
        assert EventType.AGENT_STATUS_CHANGED == "agent_status_changed"
        assert EventType.AGENT_LIFECYCLE_CHANGED == "agent_lifecycle_changed"
        assert EventType.AGENT_ERROR == "agent_error"

    def test_task_events_exist(self):
        assert EventType.TASK_CREATED == "task_created"
        assert EventType.TASK_UPDATED == "task_updated"
        assert EventType.TASK_COMPLETED == "task_completed"
        assert EventType.TASK_FAILED == "task_failed"

    def test_approval_events_exist(self):
        assert EventType.APPROVAL_CREATED == "approval_created"
        assert EventType.APPROVAL_APPROVED == "approval_approved"
        assert EventType.APPROVAL_REJECTED == "approval_rejected"

    def test_integration_events_exist(self):
        assert EventType.INTEGRATION_CONNECTED == "integration_connected"
        assert EventType.INTEGRATION_DISCONNECTED == "integration_disconnected"

    def test_tool_events_exist(self):
        assert EventType.TOOL_EXECUTION_STARTED == "tool_execution_started"
        assert EventType.TOOL_EXECUTION_COMPLETED == "tool_execution_completed"
        assert EventType.TOOL_EXECUTION_FAILED == "tool_execution_failed"


class TestDomainEvent:
    def test_agent_status_event_to_dict(self):
        event = AgentStatusEvent(
            agent_id="123",
            room_id="room-1",
            status="active",
            old_status="idle",
        )
        d = event.to_dict()
        assert d["type"] == "agent_status_changed"
        assert d["agent_id"] == "123"
        assert d["status"] == "active"
        assert d["old_status"] == "idle"
        assert "timestamp" in d

    def test_task_event_to_dict(self):
        event = TaskEvent(
            event_type=EventType.TASK_CREATED,
            task_id="t-1",
            agent_id="a-1",
            title="Do something",
            status="pending",
        )
        d = event.to_dict()
        assert d["type"] == "task_created"
        assert d["task_id"] == "t-1"
        assert d["title"] == "Do something"


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, fresh_event_bus, mock_handler):
        fresh_event_bus.subscribe("test_event", mock_handler)
        event = DomainEvent(event_type="test_event")
        await fresh_event_bus.publish(event)
        mock_handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_subscribe_all(self, fresh_event_bus, mock_handler):
        fresh_event_bus.subscribe_all(mock_handler)
        event = DomainEvent(event_type=EventType.TASK_CREATED)
        await fresh_event_bus.publish(event)
        mock_handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_unsubscribe(self, fresh_event_bus, mock_handler):
        fresh_event_bus.subscribe(EventType.AGENT_STATUS_CHANGED, mock_handler)
        fresh_event_bus.unsubscribe(EventType.AGENT_STATUS_CHANGED, mock_handler)
        event = DomainEvent(event_type=EventType.AGENT_STATUS_CHANGED)
        await fresh_event_bus.publish(event)
        mock_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, fresh_event_bus):
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        fresh_event_bus.subscribe(EventType.TASK_CREATED, handler1)
        fresh_event_bus.subscribe(EventType.TASK_CREATED, handler2)
        event = DomainEvent(event_type=EventType.TASK_CREATED)
        await fresh_event_bus.publish(event)
        handler1.assert_called_once()
        handler2.assert_called_once()

    @pytest.mark.asyncio
    async def test_handler_error_does_not_break_others(self, fresh_event_bus):
        bad_handler = AsyncMock(side_effect=RuntimeError("boom"))
        good_handler = AsyncMock()
        fresh_event_bus.subscribe(EventType.AGENT_STATUS_CHANGED, bad_handler)
        fresh_event_bus.subscribe(EventType.AGENT_STATUS_CHANGED, good_handler)
        event = DomainEvent(event_type=EventType.AGENT_STATUS_CHANGED)
        await fresh_event_bus.publish(event)
        good_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self, fresh_event_bus):
        event = DomainEvent(event_type=EventType.SYSTEM_ALERT)
        await fresh_event_bus.publish(event)  # should not raise


@pytest.mark.asyncio
async def test_publish_agent_status():
    handler = AsyncMock()
    event_bus.subscribe(EventType.AGENT_STATUS_CHANGED, handler)
    try:
        await publish_agent_status_changed(
            agent_id=uuid4(),
            room_id="room-123",
            status="active",
            old_status="idle",
        )
        assert handler.called
        event = handler.call_args[0][0]
        assert event.event_type == EventType.AGENT_STATUS_CHANGED
        assert event.data["status"] == "active"
    finally:
        event_bus.unsubscribe(EventType.AGENT_STATUS_CHANGED, handler)


@pytest.mark.asyncio
async def test_publish_task_event():
    handler = AsyncMock()
    event_bus.subscribe(EventType.TASK_CREATED, handler)
    try:
        await publish_task_event(
            event_type=EventType.TASK_CREATED,
            task_id=uuid4(),
            agent_id=uuid4(),
            title="Test task",
            status="pending",
        )
        assert handler.called
        event = handler.call_args[0][0]
        assert event.data["title"] == "Test task"
    finally:
        event_bus.unsubscribe(EventType.TASK_CREATED, handler)


@pytest.mark.asyncio
async def test_publish_approval_event():
    handler = AsyncMock()
    event_bus.subscribe(EventType.APPROVAL_CREATED, handler)
    try:
        await publish_approval_event(
            event_type=EventType.APPROVAL_CREATED,
            approval_id=uuid4(),
            agent_id=uuid4(),
            action="send_email",
            risk_level="medium",
            status="pending",
        )
        assert handler.called
        event = handler.call_args[0][0]
        assert event.data["action"] == "send_email"
    finally:
        event_bus.unsubscribe(EventType.APPROVAL_CREATED, handler)


@pytest.mark.asyncio
async def test_publish_notification():
    handler = AsyncMock()
    event_bus.subscribe(EventType.NOTIFICATION_CREATED, handler)
    try:
        await publish_notification_created(
            notification_id=uuid4(),
            user_id=uuid4(),
            notification_type="info",
            title="Hello",
            message="World",
        )
        assert handler.called
    finally:
        event_bus.unsubscribe(EventType.NOTIFICATION_CREATED, handler)


@pytest.mark.asyncio
async def test_publish_integration_event():
    handler = AsyncMock()
    event_bus.subscribe(EventType.INTEGRATION_CONNECTED, handler)
    try:
        await publish_integration_event(
            event_type=EventType.INTEGRATION_CONNECTED,
            integration_id=uuid4(),
            account_id=uuid4(),
            integration_name="gmail",
            user_id=uuid4(),
        )
        assert handler.called
    finally:
        event_bus.unsubscribe(EventType.INTEGRATION_CONNECTED, handler)


@pytest.mark.asyncio
async def test_publish_tool_execution_event():
    handler = AsyncMock()
    event_bus.subscribe(EventType.TOOL_EXECUTION_COMPLETED, handler)
    try:
        await publish_tool_execution_event(
            event_type=EventType.TOOL_EXECUTION_COMPLETED,
            approval_id=uuid4(),
            agent_id=uuid4(),
            tool_name="email_writer",
            action="send",
            status="completed",
        )
        assert handler.called
    finally:
        event_bus.unsubscribe(EventType.TOOL_EXECUTION_COMPLETED, handler)
