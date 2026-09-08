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


async def handle_telegram_message_received(event) -> None:
    """Handle TELEGRAM_MESSAGE_RECEIVED — fire integration triggers for agents
    linked to the Telegram *Account* (MTProto) integration.

    Mirrors handle_email_received: find active agents linked to the
    telegram_account integration, create an integration trigger per agent and
    let the agent runtime's reasoning pick it up.
    """
    from app.services.agent_runtime import agent_runtime
    from app.services.trigger_service import TriggerService
    from app.models.agent import AIAgent, LifecycleStatus
    from app.models.agent_integration import AgentIntegration
    from app.models.integration import Integration
    from app.database.session import SessionLocal

    if not agent_runtime.is_running:
        return

    message_id = event.data.get("message_id", "")
    chat_id = event.data.get("chat_id", "")
    chat_title = event.data.get("chat_title", "")
    sender_id = event.data.get("sender_id", "")
    text = event.data.get("text", "")
    account_id = event.data.get("account_id", "")

    db = SessionLocal()
    try:
        trigger_service = TriggerService(db)

        tg_integration = db.query(Integration).filter(
            Integration.name == "telegram_account"
        ).first()
        if not tg_integration:
            return

        q = db.query(AgentIntegration).filter(
            AgentIntegration.integration_id == tg_integration.id,
            AgentIntegration.is_active == True,
        )
        # Telegram accounts are per-agent explicit mappings — scope to the
        # account the message actually arrived on when the event carries it.
        try:
            from uuid import UUID as _UUID

            if account_id:
                q = q.filter(AgentIntegration.integration_account_id == _UUID(account_id))
        except (ValueError, TypeError):
            pass
        agent_integrations = q.all()

        for ai in agent_integrations:
            agent = db.query(AIAgent).filter(
                AIAgent.id == ai.agent_id,
                AIAgent.lifecycle_status == LifecycleStatus.ACTIVE,
            ).first()

            if not agent:
                continue

            trigger = trigger_service.fire_integration_trigger(
                agent_id=agent.id,
                integration_name="telegram_account",
                event_type="telegram_message_received",
                event_id=f"{chat_id}:{message_id}",
                payload={
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "chat_title": chat_title,
                    "sender_id": sender_id,
                    "text": text,
                    "account_id": account_id,
                },
            )

            if trigger:
                agent_id_str = str(agent.id)
                if agent_id_str in agent_runtime._loops:
                    logger.info(
                        "Telegram message trigger created for agent",
                        extra={
                            "agent_id": agent_id_str,
                            "trigger_id": str(trigger.id),
                            "chat_id": chat_id,
                            "message_id": message_id,
                        },
                    )

    finally:
        db.close()


async def handle_telegram_bot_message_received(event) -> None:
    """Handle TELEGRAM_BOT_MESSAGE_RECEIVED — fire integration triggers for
    agents linked to the connected Telegram *Bot* integration.

    Mirrors handle_telegram_message_received. The Bot monitor already fires
    its own triggers in the worker thread; this bridge covers any other
    publisher of the event and keeps the websocket/UI contract symmetric.
    Dedup: the trigger service collapses identical (agent, event_type,
    event_id) pairs that are still PENDING/PROCESSING.
    """
    from app.services.agent_runtime import agent_runtime
    from app.services.trigger_service import TriggerService
    from app.models.agent import AIAgent, LifecycleStatus
    from app.models.agent_integration import AgentIntegration
    from app.models.integration import Integration
    from app.database.session import SessionLocal

    if not agent_runtime.is_running:
        return

    message_id = event.data.get("message_id", "")
    chat_id = event.data.get("chat_id", "")
    chat_title = event.data.get("chat_title", "")
    sender_id = event.data.get("sender_id", "")
    text = event.data.get("text", "")
    account_id = event.data.get("account_id", "")

    db = SessionLocal()
    try:
        trigger_service = TriggerService(db)

        tg_integration = db.query(Integration).filter(
            Integration.name == "telegram"
        ).first()
        if not tg_integration:
            return

        q = db.query(AgentIntegration).filter(
            AgentIntegration.integration_id == tg_integration.id,
            AgentIntegration.is_active == True,
        )
        # Bots are per-agent explicit mappings — scope to the bot account the
        # customer message actually arrived on when the event carries it.
        try:
            from uuid import UUID as _UUID

            if account_id:
                q = q.filter(AgentIntegration.integration_account_id == _UUID(account_id))
        except (ValueError, TypeError):
            pass
        agent_integrations = q.all()

        for ai in agent_integrations:
            agent = db.query(AIAgent).filter(
                AIAgent.id == ai.agent_id,
                AIAgent.lifecycle_status == LifecycleStatus.ACTIVE,
            ).first()

            if not agent:
                continue

            trigger = trigger_service.fire_integration_trigger(
                agent_id=agent.id,
                integration_name="telegram",
                event_type="telegram_bot_message_received",
                event_id=f"{chat_id}:{message_id}",
                payload={
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "chat_title": chat_title,
                    "sender_id": sender_id,
                    "text": text,
                    "account_id": account_id,
                },
            )

            if trigger:
                agent_id_str = str(agent.id)
                if agent_id_str in agent_runtime._loops:
                    logger.info(
                        "Telegram bot message trigger created for agent",
                        extra={
                            "agent_id": agent_id_str,
                            "trigger_id": str(trigger.id),
                            "chat_id": chat_id,
                            "message_id": message_id,
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
    event_bus.subscribe(EventType.TELEGRAM_MESSAGE_RECEIVED, handle_telegram_message_received)
    event_bus.subscribe(EventType.TELEGRAM_BOT_MESSAGE_RECEIVED, handle_telegram_bot_message_received)
    event_bus.subscribe(EventType.TASK_CREATED, handle_task_created)
    logger.info("Trigger handlers registered")
