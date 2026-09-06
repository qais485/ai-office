"""In-process async event bus for decoupled event publishing/subscribing."""
import asyncio
import logging
from typing import Callable, Coroutine, Dict, List, Set
from app.events.types import DomainEvent, EventType

logger = logging.getLogger(__name__)

# Handler type: async callable that takes a DomainEvent
EventHandler = Callable[[DomainEvent], Coroutine]


class EventBus:
    """Async in-process event bus.

    Services publish events here. Handlers subscribe to specific event types
    or all events. Handlers run concurrently and failures are logged but
    do not block other handlers.
    """

    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._global_handlers: List[EventHandler] = []
        self._queue: asyncio.Queue[DomainEvent] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to all event types."""
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a handler subscription."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to the bus.

        If the bus is running, the event is queued for processing.
        If not running (e.g. during testing), handlers are called directly.
        """
        if self._running:
            await self._queue.put(event)
        else:
            await self._dispatch(event)

    def publish_sync(self, event: DomainEvent) -> None:
        """Schedule an event for publishing without awaiting.

        Use this from synchronous code paths. The event will be picked up
        by the background processing task.
        """
        if self._running and self._task:
            try:
                self._task.get_loop().call_soon_threadsafe(
                    self._queue.put_nowait, event
                )
            except RuntimeError:
                # Loop might be closed, fall back to direct dispatch
                asyncio.ensure_future(self._dispatch(event))
        else:
            asyncio.ensure_future(self._dispatch(event))

    async def _dispatch(self, event: DomainEvent) -> None:
        """Dispatch an event to all matching handlers."""
        handlers = list(self._handlers.get(event.event_type, []))
        handlers.extend(self._global_handlers)

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                event_name = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
                logger.error(
                    f"Handler {handler.__name__} failed for event "
                    f"{event_name}: {e}",
                    exc_info=True,
                )

    async def start(self) -> None:
        """Start the background event processing loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Event bus started")

    async def stop(self) -> None:
        """Stop the background event processing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Event bus stopped")

    async def _process_loop(self) -> None:
        """Background loop that processes events from the queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event bus processing error: {e}", exc_info=True)


# Global singleton
event_bus = EventBus()
