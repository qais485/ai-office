"""TriggerService — CRUD, validation, and execution recording for agent triggers.

Responsibilities:
    - Create/read/update/delete triggers
    - Validate agent is active before creating trigger
    - Prevent duplicate triggers (same source event + agent within cooldown)
    - Record execution attempts with full tracing
    - Find triggers that match a given event (for event-driven triggers)
    - Find triggers due for scheduled execution
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.agent import AIAgent, LifecycleStatus
from app.models.agent_trigger import AgentTrigger, TriggerType, TriggerStatus
from app.models.trigger_execution import TriggerExecution, ExecutionStatus

logger = logging.getLogger(__name__)


class TriggerService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_trigger(
        self,
        agent_id: UUID,
        trigger_type: TriggerType,
        payload: Optional[Dict[str, Any]] = None,
        source_event_type: Optional[str] = None,
        source_event_id: Optional[str] = None,
        match_integration: Optional[str] = None,
        match_event_type: Optional[str] = None,
        match_room_id: Optional[UUID] = None,
        schedule_interval_seconds: Optional[int] = None,
        cooldown_seconds: int = 30,
    ) -> AgentTrigger:
        """Create a new trigger. Validates agent exists and is active."""
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        if agent.lifecycle_status != LifecycleStatus.ACTIVE:
            raise ValueError(f"Agent {agent.name} is not active (status: {agent.lifecycle_status.value})")

        if trigger_type == TriggerType.SCHEDULED and not schedule_interval_seconds:
            raise ValueError("Scheduled triggers require schedule_interval_seconds")

        # Token saving: clamp scheduled intervals to a minimum floor — every
        # scheduled run costs one full LLM call, so sub-minute schedules are
        # almost always a misconfiguration that burns tokens 24/7.
        if trigger_type == TriggerType.SCHEDULED:
            from app.core.config import settings
            schedule_interval_seconds = max(
                int(schedule_interval_seconds), settings.MIN_SCHEDULED_INTERVAL_SECONDS
            )

        now = datetime.now(timezone.utc)
        next_run = None
        if trigger_type == TriggerType.SCHEDULED:
            next_run = now + timedelta(seconds=schedule_interval_seconds)

        trigger = AgentTrigger(
            agent_id=agent_id,
            trigger_type=trigger_type,
            status=TriggerStatus.PENDING,
            source_event_type=source_event_type,
            source_event_id=source_event_id,
            payload=payload or {},
            match_integration=match_integration,
            match_event_type=match_event_type,
            match_room_id=match_room_id,
            schedule_interval_seconds=schedule_interval_seconds,
            next_run_at=next_run,
            cooldown_seconds=cooldown_seconds,
            is_active=True,
            total_executions=0,
        )
        self.db.add(trigger)
        self.db.commit()
        self.db.refresh(trigger)

        logger.info(
            "Trigger created",
            extra={"trigger_id": str(trigger.id), "agent_id": str(agent_id), "type": trigger_type.value},
        )
        return trigger

    def get_trigger(self, trigger_id: UUID) -> Optional[AgentTrigger]:
        return self.db.query(AgentTrigger).filter(AgentTrigger.id == trigger_id).first()

    def get_triggers_for_agent(self, agent_id: UUID, active_only: bool = True) -> List[AgentTrigger]:
        q = self.db.query(AgentTrigger).filter(AgentTrigger.agent_id == agent_id)
        if active_only:
            q = q.filter(AgentTrigger.is_active == True)
        return q.all()

    def list_triggers(
        self,
        agent_id: Optional[UUID] = None,
        trigger_type: Optional[TriggerType] = None,
        active_only: bool = False,
        limit: int = 50,
    ) -> List[AgentTrigger]:
        q = self.db.query(AgentTrigger)
        if agent_id:
            q = q.filter(AgentTrigger.agent_id == agent_id)
        if trigger_type:
            q = q.filter(AgentTrigger.trigger_type == trigger_type)
        if active_only:
            q = q.filter(AgentTrigger.is_active == True)
        return q.order_by(AgentTrigger.created_at.desc()).limit(limit).all()

    def update_trigger(self, trigger_id: UUID, **kwargs) -> Optional[AgentTrigger]:
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return None
        for key, value in kwargs.items():
            if hasattr(trigger, key):
                setattr(trigger, key, value)
        self.db.commit()
        self.db.refresh(trigger)
        return trigger

    def delete_trigger(self, trigger_id: UUID) -> bool:
        trigger = self.get_trigger(trigger_id)
        if not trigger:
            return False
        self.db.delete(trigger)
        self.db.commit()
        logger.info("Trigger deleted", extra={"trigger_id": str(trigger_id)})
        return True

    def activate_trigger(self, trigger_id: UUID) -> Optional[AgentTrigger]:
        return self.update_trigger(trigger_id, is_active=True)

    def deactivate_trigger(self, trigger_id: UUID) -> Optional[AgentTrigger]:
        return self.update_trigger(trigger_id, is_active=False)

    # ------------------------------------------------------------------
    # Event matching — find triggers that should fire for a given event
    # ------------------------------------------------------------------

    def find_matching_triggers(
        self,
        event_type: str,
        integration_name: Optional[str] = None,
        room_id: Optional[UUID] = None,
    ) -> List[AgentTrigger]:
        """Find all active triggers that match the given event characteristics."""
        now = datetime.now(timezone.utc)
        q = self.db.query(AgentTrigger).filter(
            AgentTrigger.is_active == True,
            AgentTrigger.status != TriggerStatus.PROCESSING,
        )

        conditions = []

        # Integration event triggers
        if integration_name:
            conditions.append(
                and_(
                    AgentTrigger.trigger_type == TriggerType.INTEGRATION,
                    AgentTrigger.match_integration == integration_name,
                )
            )

        # Room event triggers
        if room_id:
            conditions.append(
                and_(
                    AgentTrigger.trigger_type == TriggerType.ROOM,
                    AgentTrigger.match_room_id == room_id,
                )
            )

        # General event type matching
        if event_type:
            conditions.append(
                and_(
                    AgentTrigger.match_event_type == event_type,
                    AgentTrigger.trigger_type == TriggerType.INTEGRATION,
                )
            )

        if conditions:
            from sqlalchemy import or_
            q = q.filter(or_(*conditions))

        triggers = q.all()

        # Filter by cooldown
        valid = []
        for trigger in triggers:
            if self._is_within_cooldown(trigger):
                continue
            # Verify agent is still active
            agent = self.db.query(AIAgent).filter(AIAgent.id == trigger.agent_id).first()
            if agent and agent.lifecycle_status == LifecycleStatus.ACTIVE:
                valid.append(trigger)

        return valid

    def _is_within_cooldown(self, trigger: AgentTrigger) -> bool:
        """Check if trigger is within its cooldown period."""
        if not trigger.last_run_at or not trigger.cooldown_seconds:
            return False
        now = datetime.now(timezone.utc)
        last_run = trigger.last_run_at
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        elapsed = (now - last_run).total_seconds()
        return elapsed < trigger.cooldown_seconds

    # ------------------------------------------------------------------
    # Scheduled triggers
    # ------------------------------------------------------------------

    def get_due_scheduled_triggers(self) -> List[AgentTrigger]:
        """Find all scheduled triggers that are due for execution."""
        now = datetime.now(timezone.utc)
        return self.db.query(AgentTrigger).filter(
            AgentTrigger.trigger_type == TriggerType.SCHEDULED,
            AgentTrigger.is_active == True,
            AgentTrigger.status != TriggerStatus.PROCESSING,
            AgentTrigger.next_run_at <= now,
        ).all()

    def advance_schedule(self, trigger: AgentTrigger) -> None:
        """Advance next_run_at after execution."""
        if trigger.trigger_type != TriggerType.SCHEDULED or not trigger.schedule_interval_seconds:
            return
        from app.core.config import settings
        now = datetime.now(timezone.utc)
        effective_interval = max(
            int(trigger.schedule_interval_seconds), settings.MIN_SCHEDULED_INTERVAL_SECONDS
        )
        trigger.next_run_at = now + timedelta(seconds=effective_interval)
        trigger.last_run_at = now
        self.db.commit()

    # ------------------------------------------------------------------
    # Execution recording
    # ------------------------------------------------------------------

    def start_execution(self, trigger: AgentTrigger) -> TriggerExecution:
        """Record the start of a trigger execution."""
        now = datetime.now(timezone.utc)
        execution = TriggerExecution(
            trigger_id=trigger.id,
            agent_id=trigger.agent_id,
            status=ExecutionStatus.STARTED,
            trigger_type=trigger.trigger_type.value,
            source_event_type=trigger.source_event_type,
            source_event_id=trigger.source_event_id,
            started_at=now,
        )
        self.db.add(execution)

        trigger.status = TriggerStatus.PROCESSING
        trigger.total_executions = (trigger.total_executions or 0) + 1

        self.db.commit()
        self.db.refresh(execution)

        logger.info(
            "Execution started",
            extra={
                "execution_id": str(execution.id),
                "trigger_id": str(trigger.id),
                "agent_id": str(trigger.agent_id),
                "trigger_type": trigger.trigger_type.value,
            },
        )
        return execution

    def update_execution(
        self,
        execution: TriggerExecution,
        status: Optional[ExecutionStatus] = None,
        llm_reasoning: Optional[str] = None,
        selected_tool: Optional[str] = None,
        selected_action: Optional[str] = None,
        tool_parameters: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> TriggerExecution:
        """Update an execution record."""
        now = datetime.now(timezone.utc)

        if status is not None:
            execution.status = status
        if llm_reasoning is not None:
            execution.llm_reasoning = llm_reasoning[:2000] if llm_reasoning else None
        if selected_tool is not None:
            execution.selected_tool = selected_tool
        if selected_action is not None:
            execution.selected_action = selected_action
        if tool_parameters is not None:
            execution.tool_parameters = tool_parameters
        if result is not None:
            execution.result = result
        if error_message is not None:
            execution.error_message = error_message[:2000] if error_message else None

        # Calculate duration if completing
        if status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED, ExecutionStatus.TIMEOUT):
            execution.completed_at = now
            if execution.started_at:
                started = execution.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                execution.duration_ms = int((now - started).total_seconds() * 1000)

        self.db.commit()
        self.db.refresh(execution)
        return execution

    def complete_execution(
        self,
        execution: TriggerExecution,
        trigger: AgentTrigger,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> TriggerExecution:
        """Finalize an execution record and update trigger state."""
        now = datetime.now(timezone.utc)

        if success:
            execution = self.update_execution(
                execution,
                status=ExecutionStatus.COMPLETED,
                result=result,
            )
            trigger.status = TriggerStatus.COMPLETED
            trigger.last_error = None
            trigger.last_execution_id = execution.id
        else:
            execution = self.update_execution(
                execution,
                status=ExecutionStatus.FAILED,
                result=result,
                error_message=error_message,
            )
            trigger.status = TriggerStatus.FAILED
            trigger.last_error = (error_message or "")[:500]
            trigger.last_execution_id = execution.id

        # Advance schedule if scheduled trigger
        self.advance_schedule(trigger)

        logger.info(
            "Execution completed",
            extra={
                "execution_id": str(execution.id),
                "trigger_id": str(trigger.id),
                "agent_id": str(trigger.agent_id),
                "success": success,
                "duration_ms": execution.duration_ms,
            },
        )
        return execution

    def get_executions(
        self,
        trigger_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> List[TriggerExecution]:
        """Get execution history."""
        q = self.db.query(TriggerExecution)
        if trigger_id:
            q = q.filter(TriggerExecution.trigger_id == trigger_id)
        if agent_id:
            q = q.filter(TriggerExecution.agent_id == agent_id)
        return q.order_by(TriggerExecution.created_at.desc()).limit(limit).all()

    # ------------------------------------------------------------------
    # Manual trigger shortcut
    # ------------------------------------------------------------------

    def fire_manual_trigger(
        self,
        agent_id: UUID,
        instruction: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AgentTrigger:
        """Create and immediately queue a manual trigger."""
        trigger = self.create_trigger(
            agent_id=agent_id,
            trigger_type=TriggerType.MANUAL,
            payload={"instruction": instruction, **(payload or {})},
            source_event_type="manual",
        )
        return trigger

    def fire_integration_trigger(
        self,
        agent_id: UUID,
        integration_name: str,
        event_type: str,
        event_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[AgentTrigger]:
        """Fire an integration event trigger for a specific agent.

        Returns None if trigger was suppressed (cooldown/duplicate).
        """
        agent = self.db.query(AIAgent).filter(AIAgent.id == agent_id).first()
        if not agent or agent.lifecycle_status != LifecycleStatus.ACTIVE:
            return None

        # Check cooldown — suppress if a trigger for the same event already exists
        # in PENDING or PROCESSING state (prevents duplicates from event bridge + direct creation)
        existing = self.db.query(AgentTrigger).filter(
            AgentTrigger.agent_id == agent_id,
            AgentTrigger.source_event_type == event_type,
            AgentTrigger.source_event_id == event_id,
            AgentTrigger.status.in_([TriggerStatus.PENDING, TriggerStatus.PROCESSING]),
        ).first()
        if existing:
            logger.debug("Integration trigger suppressed (duplicate)", extra={"event_id": event_id})
            return None

        trigger = self.create_trigger(
            agent_id=agent_id,
            trigger_type=TriggerType.INTEGRATION,
            payload=payload or {},
            source_event_type=event_type,
            source_event_id=event_id,
            match_integration=integration_name,
            match_event_type=event_type,
        )
        return trigger
