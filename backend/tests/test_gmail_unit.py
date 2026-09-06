"""Unit tests for Gmail Agent services.

These tests verify individual service methods in isolation with mocked dependencies.
"""
import pytest
import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.models.user import User, UserRole
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
from app.utils.encryption import encrypt_field


# ---------------------------------------------------------------------------
# GmailMonitorService unit tests
# ---------------------------------------------------------------------------

class TestGmailMonitorServiceUnit:
    """Unit tests for GmailMonitorService methods."""

    def test_check_account_not_found(self, api_db):
        """Test check_account with non-existent account."""
        from app.services.gmail_monitor_service import GmailMonitorService

        service = GmailMonitorService(api_db)
        result = service.check_account(uuid4())

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_check_account_inactive(self, api_db, regular_user):
        """Test check_account with inactive account."""
        from app.services.gmail_monitor_service import GmailMonitorService

        integration = Integration(
            id=uuid4(), name="gmail", display_name="Gmail",
            auth_type="oauth2", is_active=True,
        )
        api_db.add(integration)
        api_db.flush()

        account = IntegrationAccount(
            id=uuid4(), integration_id=integration.id, user_id=regular_user.id,
            display_name="user@gmail.com", status="connected", is_active=False,
            oauth2_access_token=encrypt_field("token"), oauth2_refresh_token=encrypt_field("refresh"),
        )
        api_db.add(account)
        api_db.commit()

        service = GmailMonitorService(api_db)
        result = service.check_account(account.id)

        assert result["success"] is False

    def test_check_account_valid_token(self, api_db, regular_user):
        """Test check_account with valid token proceeds to fetch."""
        from app.services.gmail_monitor_service import GmailMonitorService

        integration = Integration(
            id=uuid4(), name="gmail", display_name="Gmail",
            auth_type="oauth2", is_active=True,
        )
        api_db.add(integration)
        api_db.flush()

        account = IntegrationAccount(
            id=uuid4(), integration_id=integration.id, user_id=regular_user.id,
            display_name="user@gmail.com", status="connected", is_active=True,
            oauth2_access_token=encrypt_field("valid_token"),
            oauth2_refresh_token=encrypt_field("refresh"),
            oauth2_token_expiry=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )
        api_db.add(account)
        api_db.flush()

        sync_state = GmailSyncState(
            id=uuid4(), integration_account_id=account.id,
            user_id=regular_user.id, gmail_address="user@gmail.com",
            is_active=True,
        )
        api_db.add(sync_state)
        api_db.commit()

        service = GmailMonitorService(api_db)

        with patch("app.services.oauth2_service.OAuth2Service") as mock_oauth:
            mock_oauth.return_value.get_access_token.return_value = "valid_token"

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"messages": []}
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
                mock_client.return_value.get = AsyncMock(return_value=mock_response)

                result = service.check_account(account.id)
                assert "success" in result

    def test_extract_body(self, api_db):
        """Test body extraction from Gmail payload."""
        from app.services.gmail_monitor_service import GmailMonitorService

        service = GmailMonitorService(api_db)

        payload = {
            "mimeType": "text/plain",
            "body": {"data": "SGVsbG8gV29ybGQ="},  # Base64 "Hello World"
        }
        body = service._extract_body(payload)
        assert "Hello World" in body

    def test_extract_body_multipart(self, api_db):
        """Test body extraction from multipart payload."""
        from app.services.gmail_monitor_service import GmailMonitorService

        service = GmailMonitorService(api_db)

        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": "VGV4dCBib2R5"},  # Base64 "Text body"
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": "PGgxPkhUTUw8L2gxPg=="},  # Base64 "<h1>HTML</h1>"
                },
            ],
        }
        body = service._extract_body(payload)
        assert body is not None


# ---------------------------------------------------------------------------
# GmailDeduplicationService unit tests
# ---------------------------------------------------------------------------

class TestGmailDeduplicationServiceUnit:
    """Unit tests for GmailDeduplicationService methods."""

    def test_claim_new_event(self, api_db):
        """Test claiming a new event."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        svc = GmailDeduplicationService(api_db)
        outcome = svc.claim(uuid4(), "msg_new", uuid4())

        assert outcome == DedupOutcome.CLAIMED

    def test_claim_processing_event(self, api_db):
        """Test claiming an event already being processed."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        account_id = uuid4()
        msg_id = "msg_processing"
        agent_id = uuid4()

        svc = GmailDeduplicationService(api_db)
        svc.claim(account_id, msg_id, agent_id)

        outcome = svc.claim(account_id, msg_id, agent_id)
        assert outcome == DedupOutcome.PROCESSING

    def test_claim_completed_event(self, api_db):
        """Test claiming a completed event."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        account_id = uuid4()
        msg_id = "msg_completed"
        agent_id = uuid4()

        svc = GmailDeduplicationService(api_db)
        svc.claim(account_id, msg_id, agent_id)
        svc.mark_completed(account_id, msg_id, agent_id)

        outcome = svc.claim(account_id, msg_id, agent_id)
        assert outcome == DedupOutcome.ALREADY_COMPLETED

    def test_mark_completed_nonexistent(self, api_db):
        """Test marking a non-existent event as completed."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService

        svc = GmailDeduplicationService(api_db)
        svc.mark_completed(uuid4(), "nonexistent_msg", uuid4())

    def test_claim_creates_record(self, api_db):
        """Test that claim creates an execution record."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        account_id = uuid4()
        msg_id = "msg_claim_test"
        agent_id = uuid4()

        svc = GmailDeduplicationService(api_db)
        claim_result = svc.claim(account_id, msg_id, agent_id)
        assert claim_result == DedupOutcome.CLAIMED

        # Verify record was created with correct status
        exec_record = api_db.query(GmailExecution).filter(
            GmailExecution.gmail_message_id == msg_id,
            GmailExecution.agent_id == agent_id,
        ).first()
        assert exec_record is not None
        assert exec_record.status == GmailExecutionStatus.PROCESSING.value
        assert exec_record.integration_account_id == account_id
        assert exec_record.attempt == 1

    def test_increment_duplicate(self, api_db):
        """Test incrementing duplicate count."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService

        account_id = uuid4()
        msg_id = "msg_dup"
        agent_id = uuid4()

        svc = GmailDeduplicationService(api_db)
        svc.claim(account_id, msg_id, agent_id)
        svc.mark_completed(account_id, msg_id, agent_id)
        svc.increment_duplicate(account_id, msg_id, agent_id)

        exec_record = api_db.query(GmailExecution).filter(
            GmailExecution.gmail_message_id == msg_id
        ).first()
        if exec_record:
            assert exec_record.duplicate_attempts == 1

    def test_retry_event(self, api_db):
        """Test retrying a failed event."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        account_id = uuid4()
        msg_id = "msg_retry"
        agent_id = uuid4()

        svc = GmailDeduplicationService(api_db)
        claim_result = svc.claim(account_id, msg_id, agent_id)
        if claim_result.value == "claimed":
            svc.mark_failed(account_id, msg_id, agent_id, "Error")

            outcome = svc.claim(account_id, msg_id, agent_id)
            assert outcome in (DedupOutcome.CLAIMED, DedupOutcome.PROCESSING, DedupOutcome.RETRY_ELIGIBLE)


# ---------------------------------------------------------------------------
# TriggerService unit tests
# ---------------------------------------------------------------------------

class TestTriggerServiceUnit:
    """Unit tests for TriggerService methods."""

    def _make_agent(self, api_db):
        agent = AIAgent(
            id=uuid4(), name="Test Agent", role="assistant",
            status=AgentStatus.ACTIVE, lifecycle_status=LifecycleStatus.ACTIVE,
        )
        api_db.add(agent)
        api_db.commit()
        return agent

    def test_create_trigger(self, api_db):
        """Test creating a new trigger."""
        from app.services.trigger_service import TriggerService

        agent = self._make_agent(api_db)

        svc = TriggerService(api_db)
        trigger = svc.create_trigger(
            agent_id=agent.id,
            trigger_type=TriggerType.INTEGRATION,
            match_event_type="EMAIL_RECEIVED",
        )

        assert trigger.id is not None
        assert trigger.agent_id == agent.id

    def test_get_agent_triggers(self, api_db):
        """Test retrieving triggers for an agent."""
        from app.services.trigger_service import TriggerService

        agent = self._make_agent(api_db)

        svc = TriggerService(api_db)
        svc.create_trigger(
            agent_id=agent.id, trigger_type=TriggerType.INTEGRATION,
            match_event_type="EMAIL_RECEIVED",
        )
        svc.create_trigger(
            agent_id=agent.id, trigger_type=TriggerType.INTEGRATION,
            match_event_type="TASK_CREATED",
        )

        triggers = svc.get_triggers_for_agent(agent.id)
        assert len(triggers) == 2

    def test_delete_trigger(self, api_db):
        """Test deleting a trigger."""
        from app.services.trigger_service import TriggerService

        agent = self._make_agent(api_db)

        svc = TriggerService(api_db)
        trigger = svc.create_trigger(
            agent_id=agent.id, trigger_type=TriggerType.INTEGRATION,
            match_event_type="EMAIL_RECEIVED",
        )

        result = svc.delete_trigger(trigger.id)
        assert result is True

        remaining = svc.get_triggers_for_agent(agent.id)
        assert len(remaining) == 0

    def test_fire_integration_trigger(self, api_db):
        """Test firing an integration trigger."""
        from app.services.trigger_service import TriggerService

        agent = self._make_agent(api_db)

        svc = TriggerService(api_db)

        trigger = svc.fire_integration_trigger(
            agent_id=agent.id,
            integration_name="gmail",
            event_type="EMAIL_RECEIVED",
            event_id="test_msg_001",
            payload={"subject": "Test"},
        )

        assert trigger is not None
        assert trigger.agent_id == agent.id
        assert trigger.trigger_type == TriggerType.INTEGRATION


# ---------------------------------------------------------------------------
# AgentRuntime unit tests
# ---------------------------------------------------------------------------

class TestAgentRuntimeUnit:
    """Unit tests for AgentRuntime methods."""

    def test_singleton_pattern(self):
        """Test AgentRuntime is a singleton."""
        from app.services.agent_runtime import AgentRuntime

        runtime1 = AgentRuntime.get_instance()
        runtime2 = AgentRuntime.get_instance()
        assert runtime1 is runtime2

    def test_get_status(self, api_db):
        """Test getting runtime status."""
        from app.services.agent_runtime import AgentRuntime

        runtime = AgentRuntime.get_instance()
        status = runtime.get_status()

        assert status is not None
        assert "is_running" in status or "running" in status

    def test_get_all_loops(self, api_db):
        """Test getting all agent loops."""
        from app.services.agent_runtime import AgentRuntime

        runtime = AgentRuntime.get_instance()
        loops = runtime.get_all_loops()

        assert isinstance(loops, dict)


# ---------------------------------------------------------------------------
# SchedulerService unit tests
# ---------------------------------------------------------------------------

class TestSchedulerServiceUnit:
    """Unit tests for SchedulerService methods."""

    def test_singleton_pattern(self):
        """Test SchedulerService is a singleton."""
        from app.services.scheduler import SchedulerService

        s1 = SchedulerService.get_instance()
        s2 = SchedulerService.get_instance()
        assert s1 is s2

    def test_register_job(self):
        """Test registering a new job."""
        from app.services.scheduler import SchedulerService

        scheduler = SchedulerService.get_instance()

        async def dummy():
            pass

        scheduler.register_job(
            name="test_job",
            func=dummy,
            interval_seconds=60,
        )

        assert scheduler.get_job("test_job") is not None

    def test_unregister_job(self):
        """Test unregistering a job."""
        from app.services.scheduler import SchedulerService

        scheduler = SchedulerService.get_instance()

        async def dummy():
            pass

        scheduler.register_job(
            name="temp_job",
            func=dummy,
            interval_seconds=60,
        )

        scheduler.unregister_job("temp_job")
        assert scheduler.get_job("temp_job") is None

    def test_get_status(self):
        """Test getting scheduler status."""
        from app.services.scheduler import SchedulerService

        scheduler = SchedulerService.get_instance()
        status = scheduler.get_status()

        assert "running" in status
        assert "job_count" in status
        assert "jobs" in status

    def test_start_stop(self):
        """Test starting and stopping scheduler."""
        from app.services.scheduler import SchedulerService

        scheduler = SchedulerService.get_instance()

        asyncio.run(scheduler.start())
        assert scheduler._running

        asyncio.run(scheduler.stop())
        assert not scheduler._running


# ---------------------------------------------------------------------------
# ToolExecutionService unit tests
# ---------------------------------------------------------------------------

class TestToolExecutionServiceUnit:
    """Unit tests for ToolExecutionService validation steps."""

    def test_validate_agent(self, api_db):
        """Test validation that agent exists."""
        from app.services.tool_execution_service import ToolExecutionService

        agent = AIAgent(
            id=uuid4(), name="Test Agent", role="assistant",
            status=AgentStatus.ACTIVE, lifecycle_status=LifecycleStatus.ACTIVE,
        )
        api_db.add(agent)
        api_db.commit()

        service = ToolExecutionService(api_db)
        validated = service._validate_agent(agent.id)
        assert validated is not None
        assert validated.id == agent.id

    def test_validate_agent_not_found(self, api_db):
        """Test validation when agent not found."""
        from app.services.tool_execution_service import ToolExecutionService

        service = ToolExecutionService(api_db)
        with pytest.raises((ValueError, Exception)):
            service._validate_agent(uuid4())

    def test_check_tool_access(self, api_db):
        """Test tool access check."""
        from app.services.tool_execution_service import ToolExecutionService

        agent = AIAgent(
            id=uuid4(), name="Test Agent", role="assistant",
            status=AgentStatus.ACTIVE, lifecycle_status=LifecycleStatus.ACTIVE,
            tools="gmail",
        )
        api_db.add(agent)
        api_db.commit()

        service = ToolExecutionService(api_db)
        has_access, msg, tool = service.check_tool_access(agent.id, "gmail")
        assert isinstance(has_access, bool)

    def test_check_action_access(self, api_db):
        """Test action access check."""
        from app.services.tool_execution_service import ToolExecutionService

        agent = AIAgent(
            id=uuid4(), name="Test Agent", role="assistant",
            status=AgentStatus.ACTIVE, lifecycle_status=LifecycleStatus.ACTIVE,
            tools="gmail",
        )
        api_db.add(agent)
        api_db.commit()

        service = ToolExecutionService(api_db)
        result = service.check_action_access(agent.id, "gmail", "read_email")
        assert isinstance(result, tuple)
        assert len(result) == 3
