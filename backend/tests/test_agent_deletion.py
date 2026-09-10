# -*- coding: utf-8 -*-
"""Regression tests for agent deletion FK cleanup (Fix.md bug).

Deleting an agent used to fail with ForeignKeyViolation because dependent
rows (agent_triggers, trigger_executions, tasks, approvals, ...) were never
cleaned up and the live Postgres FKs have no ON DELETE CASCADE.
"""
from uuid import uuid4

import pytest

from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.agent_trigger import AgentTrigger, TriggerType, TriggerStatus
from app.models.approval import Approval
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.models.room import OfficeRoom, RoomStatus, RoomVisualStatus
from app.models.task import Task, TaskStatus
from app.models.trigger_execution import TriggerExecution, ExecutionStatus
from app.services.agent_service import AgentService
from app.services.hiring_service import HiringService
from app.services.trigger_service import TriggerService

from tests.test_telegram_account_tool import _make_user


def _make_agent(api_db, user):
    room = OfficeRoom(
        id=uuid4(),
        name=f"Room {uuid4().hex[:8]}",
        description="Test room",
        status=RoomStatus.AVAILABLE,
        visual_status=RoomVisualStatus.OFFLINE,
        room_type="workspace",
        capacity="1",
    )
    api_db.add(room)
    agent = AIAgent(
        id=uuid4(),
        name=f"Agent {uuid4().hex[:6]}",
        role="assistant",
        description="deletable agent",
        status=AgentStatus.ACTIVE,
        lifecycle_status=LifecycleStatus.ACTIVE,
        room_id=room.id,
        user_id=user.id,
        tools="",
    )
    api_db.add(agent)
    api_db.flush()
    return agent


class TestAgentDeletionCascade:
    def test_delete_agent_with_triggers_and_executions(self, api_db):
        """The exact Fix.md failure: agent with agent_triggers rows."""
        user = _make_user(api_db, email="del1@test.com")
        agent = _make_agent(api_db, user)

        trigger_service = TriggerService(api_db)
        trigger = trigger_service.create_trigger(
            agent_id=agent.id,
            trigger_type=TriggerType.MANUAL,
            payload={"instruction": "hi"},
            source_event_type="manual",
        )
        execution = trigger_service.start_execution(trigger)
        execution_id = execution.id

        assert HiringService(api_db).delete_agent(agent.id) is True
        api_db.expire_all()
        assert api_db.query(AIAgent).filter(AIAgent.id == agent.id).first() is None
        assert api_db.query(AgentTrigger).filter(AgentTrigger.agent_id == agent.id).count() == 0
        assert api_db.query(TriggerExecution).filter(TriggerExecution.id == execution_id).first() is None

    def test_delete_agent_with_tasks_and_approvals(self, api_db):
        """tasks <-> approvals circular pair must not block the delete."""
        user = _make_user(api_db, email="del2@test.com")
        agent = _make_agent(api_db, user)

        task = Task(
            id=uuid4(), agent_id=agent.id, title="t", description="d",
            status=TaskStatus.COMPLETED,
        )
        api_db.add(task)
        api_db.flush()
        approval = Approval(
            id=uuid4(), agent_id=agent.id, task_id=task.id,
            action="send_message", parameters={}, risk_level="medium",
            status="pending",
        )
        api_db.add(approval)
        api_db.flush()
        task.approval_id = approval.id
        api_db.commit()

        assert HiringService(api_db).delete_agent(agent.id) is True
        assert api_db.query(AIAgent).filter(AIAgent.id == agent.id).first() is None
        assert api_db.query(Task).filter(Task.agent_id == agent.id).count() == 0
        assert api_db.query(Approval).filter(Approval.agent_id == agent.id).count() == 0

    def test_delete_agent_detaches_integration_account(self, api_db):
        """A nullable agent_id on an integration account is nulled, not deleted."""
        user = _make_user(api_db, email="del3@test.com")
        agent = _make_agent(api_db, user)
        integration = api_db.query(Integration).filter(Integration.name == "telegram").first()

        account = IntegrationAccount(
            integration_id=integration.id,
            user_id=user.id,
            display_name="acc",
            credentials={},
            status="connected",
            is_active=True,
            agent_id=agent.id,
        )
        api_db.add(account)
        api_db.commit()

        assert HiringService(api_db).delete_agent(agent.id) is True
        api_db.expire_all()
        fresh = api_db.query(IntegrationAccount).filter(IntegrationAccount.id == account.id).first()
        assert fresh is not None
        assert fresh.agent_id is None

    def test_agent_service_delete_uses_full_cascade(self, api_db):
        """/agents/{id} DELETE path (AgentService) must not hit FK violations."""
        user = _make_user(api_db, email="del4@test.com")
        agent = _make_agent(api_db, user)

        trigger_service = TriggerService(api_db)
        trigger_service.create_trigger(
            agent_id=agent.id,
            trigger_type=TriggerType.MANUAL,
            payload={"instruction": "x"},
            source_event_type="manual",
        )

        assert AgentService(api_db).delete_agent(agent.id, user_id=user.id) is True
        assert api_db.query(AIAgent).filter(AIAgent.id == agent.id).first() is None
        assert api_db.query(AgentTrigger).filter(AgentTrigger.agent_id == agent.id).count() == 0
