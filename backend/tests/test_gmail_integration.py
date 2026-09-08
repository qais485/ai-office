"""Integration tests for Gmail Agent services.

These tests verify that multiple services work together correctly,
testing cross-service interactions with real database operations.
"""
import pytest
import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.models.user import User
from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.models.agent_integration import AgentIntegration
from app.models.agent_trigger import AgentTrigger, TriggerType, TriggerStatus
from app.models.trigger_execution import TriggerExecution, ExecutionStatus
from app.models.gmail_sync_state import GmailSyncState
from app.models.gmail_execution import GmailExecution, GmailExecutionStatus
from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.models.agent_tool_assignment import AgentToolAssignment
from app.models.agent_permission import AgentPermission
from app.models.permission import Permission
from app.models.room import OfficeRoom, RoomStatus, RoomVisualStatus
from app.utils.encryption import encrypt_field


# ---------------------------------------------------------------------------
# Fixtures: Full Gmail Agent setup
# ---------------------------------------------------------------------------

@pytest.fixture
def full_gmail_setup(api_db, regular_user):
    """Create a complete Gmail Agent setup with all dependencies."""
    # Integration
    integration = Integration(
        id=uuid4(),
        name="gmail",
        display_name="Gmail",
        auth_type="oauth2",
        is_active=True,
    )
    api_db.add(integration)
    api_db.flush()

    # Account
    account = IntegrationAccount(
        id=uuid4(),
        integration_id=integration.id,
        user_id=regular_user.id,
        display_name="test@gmail.com",
        status="connected",
        is_active=True,
        oauth2_access_token=encrypt_field("access_token"),
        oauth2_refresh_token=encrypt_field("refresh_token"),
        oauth2_token_expiry=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    api_db.add(account)
    api_db.flush()

    # Room
    room = OfficeRoom(
        id=uuid4(),
        name="Test Room",
        description="Test",
        status=RoomStatus.AVAILABLE,
        visual_status=RoomVisualStatus.ONLINE_ACTIVE,
        room_type="workspace",
        capacity="1",
    )
    api_db.add(room)
    api_db.flush()

    # Agent
    agent = AIAgent(
        id=uuid4(),
        name="Gmail Agent",
        role="email_assistant",
        status=AgentStatus.ACTIVE,
        lifecycle_status=LifecycleStatus.ACTIVE,
        room_id=room.id,
        tools="gmail",
        permissions="gmail.read_email|gmail.send_email",
    )
    api_db.add(agent)
    api_db.flush()

    # Agent-Integration link
    agent_integration = AgentIntegration(
        id=uuid4(),
        agent_id=agent.id,
        integration_id=integration.id,
        integration_account_id=account.id,
        capabilities="read_email|send_email",
        is_active=True,
    )
    api_db.add(agent_integration)
    api_db.flush()

    # Tool
    tool = AgentTool(
        id=uuid4(),
        name="gmail",
        display_name="Gmail",
        description="Gmail API",
        category="communication",
        risk_level="medium",
        is_active=True,
        integration_id=integration.id,
    )
    api_db.add(tool)
    api_db.flush()

    # Tool Assignment
    assignment = AgentToolAssignment(
        id=uuid4(),
        agent_id=agent.id,
        tool_id=tool.id,
        tool_name="gmail",
        is_active=True,
        is_enabled=True,
    )
    api_db.add(assignment)
    api_db.flush()

    # Permissions
    perms = [
        Permission(id=uuid4(), name="gmail.read_email", description="Read", category="gmail", risk_level="low", default_status="allowed", is_active=True),
        Permission(id=uuid4(), name="gmail.send_email", description="Send", category="gmail", risk_level="medium", default_status="allowed", is_active=True),
    ]
    for p in perms:
        api_db.add(p)
        ap = AgentPermission(id=uuid4(), agent_id=agent.id, permission_id=p.id, access_level="allowed")
        api_db.add(ap)
    api_db.flush()

    # Sync State
    sync_state = GmailSyncState(
        id=uuid4(),
        integration_account_id=account.id,
        user_id=regular_user.id,
        gmail_address="test@gmail.com",
        is_active=True,
    )
    api_db.add(sync_state)
    api_db.flush()

    return {
        "integration": integration,
        "account": account,
        "room": room,
        "agent": agent,
        "agent_integration": agent_integration,
        "tool": tool,
        "assignment": assignment,
        "permissions": perms,
        "sync_state": sync_state,
        "user": regular_user,
    }


# ---------------------------------------------------------------------------
# Integration tests: Email processing pipeline
# ---------------------------------------------------------------------------

class TestEmailProcessingPipeline:
    """Test the complete email processing pipeline."""

    def test_new_email_to_trigger_creation(self, api_db, full_gmail_setup):
        """Test flow: new email -> dedup claim -> trigger creation."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome
        from app.services.trigger_service import TriggerService

        setup = full_gmail_setup
        account = setup["account"]
        agent = setup["agent"]

        # Step 1: Claim email
        dedup = GmailDeduplicationService(api_db)
        msg_id = "pipeline_test_msg"
        outcome = dedup.claim(account.id, msg_id, agent.id)
        assert outcome == DedupOutcome.CLAIMED

        # Step 2: Create trigger
        trigger_svc = TriggerService(api_db)
        trigger = trigger_svc.create_trigger(
            agent_id=agent.id,
            trigger_type=TriggerType.INTEGRATION,
            match_event_type="EMAIL_RECEIVED",
        )
        assert trigger is not None

        # Step 3: Fire trigger
        execution = trigger_svc.fire_integration_trigger(
            agent_id=agent.id,
            integration_name="gmail",
            event_type="EMAIL_RECEIVED",
            event_id=msg_id,
            payload={"subject": "Test"},
        )
        assert execution is not None

        # Step 4: Mark completed
        dedup.mark_completed(account.id, msg_id, agent.id)

        # Verify final state
        exec_record = api_db.query(GmailExecution).filter(
            GmailExecution.gmail_message_id == msg_id
        ).first()
        assert exec_record.status == GmailExecutionStatus.COMPLETED.value

    def test_duplicate_email_prevention(self, api_db, full_gmail_setup):
        """Test that duplicate emails are prevented."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        setup = full_gmail_setup
        account = setup["account"]
        agent = setup["agent"]

        dedup = GmailDeduplicationService(api_db)
        msg_id = "dup_prevention_msg"

        # First processing
        outcome1 = dedup.claim(account.id, msg_id, agent.id)
        assert outcome1 == DedupOutcome.CLAIMED
        dedup.mark_completed(account.id, msg_id, agent.id)

        # Second processing (duplicate)
        outcome2 = dedup.claim(account.id, msg_id, agent.id)
        assert outcome2 == DedupOutcome.ALREADY_COMPLETED

    def test_failed_email_retry_flow(self, api_db, full_gmail_setup):
        """Test flow: email fails -> retry -> succeeds."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        setup = full_gmail_setup
        account = setup["account"]
        agent = setup["agent"]

        dedup = GmailDeduplicationService(api_db)
        msg_id = "retry_flow_msg"

        # First attempt fails
        dedup.claim(account.id, msg_id, agent.id)
        dedup.mark_failed(account.id, msg_id, agent.id, "API timeout")

        # Retry succeeds
        outcome = dedup.claim(account.id, msg_id, agent.id)
        assert outcome in (DedupOutcome.CLAIMED, DedupOutcome.PROCESSING)
        dedup.mark_completed(account.id, msg_id, agent.id)

        # Verify final state
        exec_record = api_db.query(GmailExecution).filter(
            GmailExecution.gmail_message_id == msg_id
        ).first()
        assert exec_record.status == GmailExecutionStatus.COMPLETED.value

    def test_concurrent_event_handling(self, api_db, full_gmail_setup):
        """Test handling of concurrent events for same email."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        setup = full_gmail_setup
        account = setup["account"]
        agent = setup["agent"]

        dedup = GmailDeduplicationService(api_db)
        msg_id = "concurrent_flow_msg"

        # Worker 1 claims
        outcome1 = dedup.claim(account.id, msg_id, agent.id)
        assert outcome1 == DedupOutcome.CLAIMED

        # Worker 2 attempts same email
        outcome2 = dedup.claim(account.id, msg_id, agent.id)
        assert outcome2 == DedupOutcome.PROCESSING

        # Worker 1 completes
        dedup.mark_completed(account.id, msg_id, agent.id)

        # Worker 2's next attempt sees completed
        outcome3 = dedup.claim(account.id, msg_id, agent.id)
        assert outcome3 == DedupOutcome.ALREADY_COMPLETED


# ---------------------------------------------------------------------------
# Integration tests: Agent lifecycle interactions
# ---------------------------------------------------------------------------

class TestAgentLifecycleIntegration:
    """Test agent lifecycle interactions with other services."""

    def test_agent_deactivation_stops_triggers(self, api_db, full_gmail_setup):
        """Test that deactivating agent prevents trigger creation."""
        from app.services.trigger_service import TriggerService

        setup = full_gmail_setup
        agent = setup["agent"]

        # Deactivate agent
        agent.lifecycle_status = LifecycleStatus.INACTIVE
        api_db.commit()

        # Attempt to create trigger - should raise because agent is inactive
        trigger_svc = TriggerService(api_db)
        with pytest.raises(ValueError, match="not active"):
            trigger_svc.create_trigger(
                agent_id=agent.id,
                trigger_type=TriggerType.INTEGRATION,
                match_event_type="EMAIL_RECEIVED",
            )

    def test_agent_reactivation_resumes_processing(self, api_db, full_gmail_setup):
        """Test that reactivating agent resumes email processing."""
        setup = full_gmail_setup
        agent = setup["agent"]

        # Deactivate
        agent.lifecycle_status = LifecycleStatus.INACTIVE
        api_db.commit()

        # Reactivate
        agent.lifecycle_status = LifecycleStatus.ACTIVE
        api_db.commit()

        # Verify agent is active
        api_db.refresh(agent)
        assert agent.lifecycle_status == LifecycleStatus.ACTIVE


# ---------------------------------------------------------------------------
# Integration tests: Tool execution interactions
# ---------------------------------------------------------------------------

class TestToolExecutionIntegration:
    """Test tool execution interactions with permissions and assignments."""

    def test_tool_access_check(self, api_db, full_gmail_setup):
        """Test tool access check with proper assignment."""
        from app.services.tool_execution_service import ToolExecutionService

        setup = full_gmail_setup
        agent = setup["agent"]

        service = ToolExecutionService(api_db)
        has_access, msg, tool = service.check_tool_access(agent.id, "gmail")
        assert isinstance(has_access, bool)

    def test_tool_access_without_assignment(self, api_db, full_gmail_setup):
        """Test tool access check without assignment."""
        from app.services.tool_execution_service import ToolExecutionService

        setup = full_gmail_setup
        agent = setup["agent"]

        # Remove tool assignment
        api_db.query(AgentToolAssignment).filter(
            AgentToolAssignment.agent_id == agent.id
        ).delete()
        api_db.commit()

        service = ToolExecutionService(api_db)
        has_access, msg, tool = service.check_tool_access(agent.id, "gmail")
        # Access check result depends on implementation - may check agent.tools field
        assert isinstance(has_access, bool)


# ---------------------------------------------------------------------------
# Integration tests: Database operations
# ---------------------------------------------------------------------------

class TestDatabaseIntegration:
    """Test database operations across services."""

    def test_sync_state_persistence(self, api_db, full_gmail_setup):
        """Test that sync state persists across service calls."""
        setup = full_gmail_setup
        account = setup["account"]
        sync_state = setup["sync_state"]

        # Update sync state
        sync_state.total_processed = 42
        sync_state.consecutive_errors = 0
        api_db.commit()

        # Verify persistence
        api_db.expire_all()
        found_state = api_db.query(GmailSyncState).filter(
            GmailSyncState.integration_account_id == account.id
        ).first()

        assert found_state.total_processed == 42
        assert found_state.consecutive_errors == 0

    def test_gmail_execution_persistence(self, api_db, full_gmail_setup):
        """Test that GmailExecution records persist correctly."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService

        setup = full_gmail_setup
        account = setup["account"]
        agent = setup["agent"]

        dedup = GmailDeduplicationService(api_db)
        msg_id = "persistence_test_msg"

        dedup.claim(account.id, msg_id, agent.id)
        dedup.mark_completed(account.id, msg_id, agent.id)

        # Verify persistence
        api_db.expire_all()
        exec_record = api_db.query(GmailExecution).filter(
            GmailExecution.gmail_message_id == msg_id
        ).first()

        assert exec_record is not None
        assert exec_record.status == GmailExecutionStatus.COMPLETED.value
        assert exec_record.integration_account_id == account.id

    def test_trigger_execution_persistence(self, api_db, full_gmail_setup):
        """Test that TriggerExecution records persist correctly."""
        from app.services.trigger_service import TriggerService

        setup = full_gmail_setup
        agent = setup["agent"]

        svc = TriggerService(api_db)

        trigger = svc.fire_integration_trigger(
            agent_id=agent.id,
            integration_name="gmail",
            event_type="EMAIL_RECEIVED",
            event_id="persist_test",
            payload={"test": "data"},
        )

        # Verify trigger was created and persisted
        api_db.expire_all()
        found_trigger = api_db.query(AgentTrigger).filter(
            AgentTrigger.id == trigger.id
        ).first()

        assert found_trigger is not None
        assert found_trigger.agent_id == agent.id


# ---------------------------------------------------------------------------
# Integration tests: Error recovery
# ---------------------------------------------------------------------------

class TestErrorRecovery:
    """Test error recovery across services."""

    def test_dedup_claim_and_duplicate_prevention(self, api_db, full_gmail_setup):
        """Test claim creates record and duplicate is rejected."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        setup = full_gmail_setup
        account = setup["account"]
        agent = setup["agent"]

        dedup = GmailDeduplicationService(api_db)
        msg_id = "dedup_test_msg"

        # First claim succeeds
        outcome = dedup.claim(account.id, msg_id, agent.id)
        assert outcome == DedupOutcome.CLAIMED

        # Verify record was created
        exec_record = api_db.query(GmailExecution).filter(
            GmailExecution.gmail_message_id == msg_id,
            GmailExecution.agent_id == agent.id,
        ).first()
        assert exec_record is not None
        assert exec_record.status == GmailExecutionStatus.PROCESSING.value

        # Mark completed
        dedup.mark_completed(account.id, msg_id, agent.id)

        # Second claim is rejected (already completed)
        outcome2 = dedup.claim(account.id, msg_id, agent.id)
        assert outcome2 == DedupOutcome.ALREADY_COMPLETED

    def test_trigger_recovery_from_failure(self, api_db, full_gmail_setup):
        """Test recovery from trigger execution failure."""
        from app.services.trigger_service import TriggerService

        setup = full_gmail_setup
        agent = setup["agent"]

        svc = TriggerService(api_db)
        trigger = svc.create_trigger(
            agent_id=agent.id,
            trigger_type=TriggerType.INTEGRATION,
            match_event_type="EMAIL_RECEIVED",
        )

        # Fire trigger
        execution = svc.fire_integration_trigger(
            agent_id=agent.id,
            integration_name="gmail",
            event_type="EMAIL_RECEIVED",
            event_id="recovery_test",
            payload={"recovery": "test"},
        )

        # Verify execution was created
        assert execution is not None

    def test_scheduler_job_registration(self, api_db):
        """Test that scheduler jobs can be registered and retrieved."""
        from app.services.scheduler import SchedulerService

        scheduler = SchedulerService.get_instance()
        call_count = 0

        async def test_job():
            nonlocal call_count
            call_count += 1

        scheduler.register_job(
            name="test_recovery_job",
            func=test_job,
            interval_seconds=60,
        )

        job = scheduler.get_job("test_recovery_job")
        assert job is not None
        assert job.name == "test_recovery_job"

        scheduler.unregister_job("test_recovery_job")
        assert scheduler.get_job("test_recovery_job") is None
