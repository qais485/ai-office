"""Event-to-Trigger bridge — converts domain events into persisted agent triggers.

This module subscribes to domain events and routes them to the appropriate
agent triggers via TriggerService. It ensures:
    - Only active agents with matching triggers receive events
    - Duplicate triggers are prevented via TriggerService cooldown
    - Events are properly mapped to trigger types
    - All executions are recorded with execution IDs
"""
import logging
import uuid
from typing import Optional
from datetime import datetime, timezone

from app.models.agent_trigger import TriggerType

logger = logging.getLogger(__name__)


async def handle_email_received(event) -> None:
    """Handle EMAIL_RECEIVED event — fire integration triggers for matching agents."""
    from app.services.agent_runtime import agent_runtime
    from app.services.trigger_service import TriggerService
    from app.models.agent import AIAgent, LifecycleStatus
    from app.models.agent_integration import AgentIntegration
    from app.models.integration import Integration
    from app.database.session import SessionLocal

    if not agent_runtime.is_running:
        return

    email_id = event.data.get("email_id", "")
    from_address = event.data.get("from_address", "")
    subject = event.data.get("subject", "")
    account_id = event.data.get("account_id", "")

    db = SessionLocal()
    try:
        trigger_service = TriggerService(db)

        # Find agents with integration triggers that match "gmail"
        gmail_integration = db.query(Integration).filter(Integration.name == "gmail").first()
        if gmail_integration:
            agent_integrations = db.query(AgentIntegration).filter(
                AgentIntegration.integration_id == gmail_integration.id,
                AgentIntegration.is_active == True,
            ).all()

            for ai in agent_integrations:
                agent = db.query(AIAgent).filter(
                    AIAgent.id == ai.agent_id,
                    AIAgent.lifecycle_status == LifecycleStatus.ACTIVE,
                ).first()

                if not agent:
                    continue

                trigger = trigger_service.fire_integration_trigger(
                    agent_id=agent.id,
                    integration_name="gmail",
                    event_type="email_received",
                    event_id=email_id,
                    payload={
                        "email_id": email_id,
                        "from_address": from_address,
                        "subject": subject,
                        "account_id": account_id,
                    },
                )

                if trigger:
                    # Agent loop will pick up the pending trigger on next poll
                    agent_id_str = str(agent.id)
                    if agent_id_str in agent_runtime._loops:
                        logger.info(
                            "Email trigger created for agent",
                            extra={
                                "agent_id": agent_id_str,
                                "trigger_id": str(trigger.id),
                                "email_id": email_id,
                                "subject": subject,
                            },
                        )

    finally:
        db.close()


async def handle_task_created(event) -> None:
    """Handle TASK_CREATED event — fire trigger for the assigned agent."""
    from app.services.agent_runtime import agent_runtime
    from app.services.trigger_service import TriggerService
    from app.models.agent import AIAgent, LifecycleStatus
    from app.database.session import SessionLocal

    if not agent_runtime.is_running:
        return

    task_id = event.data.get("task_id", "")
    agent_id = event.data.get("agent_id", "")
    title = event.data.get("title", "")
    priority = event.data.get("priority", "medium")

    if not agent_id:
        return

    # Loop guard — self-sustaining cycle prevention:
    # trigger processing → _create_execution_task → TASK_CREATED → this handler
    # → new trigger → ... Each cycle costs an LLM call and several DB connections,
    # starving the pool so login/API requests hang. Only user-facing task
    # creations (real task service) may fire agent triggers; the runtime's own
    # execution bookkeeping tasks must not.
    if event.data.get("is_execution_bookkeeping"):
        logger.debug(
            "Ignoring TASK_CREATED for runtime bookkeeping task %s (loop prevention)",
            event.data.get("task_id"),
        )
        return

    db = SessionLocal()
    try:
        trigger_service = TriggerService(db)

        agent = db.query(AIAgent).filter(
            AIAgent.id == agent_id,
            AIAgent.lifecycle_status == LifecycleStatus.ACTIVE,
        ).first()

        if not agent:
            return

        # Cross-source dedup: skip if a trigger for this source event already exists
        from app.models.agent_trigger import AgentTrigger, TriggerStatus

        dup = db.query(AgentTrigger).filter(
            AgentTrigger.agent_id == agent_id,
            AgentTrigger.source_event_type == "task_created",
            AgentTrigger.source_event_id == task_id,
            AgentTrigger.status.in_([TriggerStatus.PENDING, TriggerStatus.PROCESSING]),
        ).first()
        if dup:
            logger.debug(
                "Duplicate task trigger skipped (existing trigger %s for task %s)",
                str(dup.id),
                task_id,
            )
            return

        trigger = trigger_service.create_trigger(
            agent_id=agent.id,
            trigger_type=TriggerType.INTEGRATION,
            payload={
                "task_id": task_id,
                "title": title,
                "priority": priority,
                "description": event.data.get("description", ""),
            },
            source_event_type="task_created",
            source_event_id=task_id,
            match_event_type="task_created",
        )

        logger.info(
            "Task trigger created for agent",
            extra={
                "agent_id": str(agent.id),
                "trigger_id": str(trigger.id),
                "task_id": task_id,
                "title": title,
            },
        )

    finally:
        db.close()


def register_trigger_handlers() -> None:
    """Register all trigger handlers with the event bus."""
    from app.events.bus import event_bus
    from app.events.types import EventType

    event_bus.subscribe(EventType.EMAIL_RECEIVED, handle_email_received)
    event_bus.subscribe(EventType.TASK_CREATED, handle_task_created)
    logger.info("Trigger handlers registered")
