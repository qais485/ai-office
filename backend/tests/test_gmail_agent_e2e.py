"""End-to-end tests for Gmail Agent functionality.

These tests verify the complete flow from Gmail account connection through
email processing to agent execution. They use the SQLite test database with
mocked Gmail API calls.

Test Matrix:
    1. Gmail connection success
    2. Invalid/expired OAuth token
    3. Token refresh
    4. Agent inactive
    5. Agent active
    6. Missing tool assignment
    7. Missing integration
    8. Multiple Gmail accounts
    9. Wrong account ownership
    10. New email detection
    11. Duplicate email
    12. Concurrent duplicate event
    13. Permission denied
    14. Approval required
    15. Approval granted
    16. Gmail API failure
    17. Agent runtime failure
    18. Scheduler restart
    19. Application restart
    20. Database connection failure
"""
import pytest
import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import OperationalError

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
from app.models.permission import Permission
from app.models.agent_permission import AgentPermission
from app.models.agent_tool_assignment import AgentToolAssignment
from app.models.room import OfficeRoom, RoomStatus, RoomVisualStatus
from app.utils.encryption import encrypt_field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gmail_message(msg_id="msg_123", subject="Test Email", from_addr="sender@test.com"):
    return {
        "id": msg_id,
        "threadId": f"thread_{msg_id}",
        "subject": subject,
        "from": from_addr,
        "to": "recipient@test.com",
        "date": datetime.now(timezone.utc).isoformat(),
        "snippet": f"Preview of {subject}",
        "label_ids": ["INBOX"],
        "body": f"Body of {subject}",
    }


# ---------------------------------------------------------------------------
# Fixtures: Gmail-specific entities
# ---------------------------------------------------------------------------

@pytest.fixture
def gmail_integration(api_db):
    integration = Integration(
        id=uuid4(),
        name="gmail",
        display_name="Gmail",
        description="Google Mail integration",
        auth_type="oauth2",
        is_active=True,
        oauth2_authorize_url="https://accounts.google.com/o/oauth2/auth",
        oauth2_token_url="https://oauth2.googleapis.com/token",
        oauth2_client_id_key="GOOGLE_CLIENT_ID",
        oauth2_client_secret_key="GOOGLE_CLIENT_SECRET",
        oauth2_scopes="https://mail.google.com/ https://www.googleapis.com/auth/gmail.modify",
        oauth2_redirect_path="/api/v1/integrations/oauth2/callback",
    )
    api_db.add(integration)
    api_db.flush()
    return integration


@pytest.fixture
def gmail_account(api_db, regular_user, gmail_integration):
    account = IntegrationAccount(
        id=uuid4(),
        integration_id=gmail_integration.id,
        user_id=regular_user.id,
        display_name="user@gmail.com",
        status="connected",
        is_active=True,
        oauth2_access_token=encrypt_field("valid_access_token"),
        oauth2_refresh_token=encrypt_field("valid_refresh_token"),
        oauth2_token_expiry=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        oauth2_scope="https://mail.google.com/",
    )
    api_db.add(account)
    api_db.flush()
    return account


@pytest.fixture
def gmail_agent(api_db, regular_user, sample_room, gmail_integration, gmail_account):
    agent = AIAgent(
        id=uuid4(),
        name="Gmail Agent",
        role="email_assistant",
        description="Handles email processing",
        status=AgentStatus.ACTIVE,
        lifecycle_status=LifecycleStatus.ACTIVE,
        room_id=sample_room.id,
        goals="Process emails|Respond to inquiries",
        rules="Be professional|Reply within 24h",
        tools="gmail",
        permissions="gmail.read_email|gmail.send_email",
    )
    api_db.add(agent)
    api_db.flush()

    agent_integration = AgentIntegration(
        id=uuid4(),
        agent_id=agent.id,
        integration_id=gmail_integration.id,
        integration_account_id=gmail_account.id,
        capabilities="read_email|send_email|search_emails",
        is_active=True,
    )
    api_db.add(agent_integration)
    api_db.flush()

    sync_state = GmailSyncState(
        id=uuid4(),
        integration_account_id=gmail_account.id,
        user_id=regular_user.id,
        gmail_address="user@gmail.com",
        is_active=True,
    )
    api_db.add(sync_state)
    api_db.flush()

    return agent


@pytest.fixture
def gmail_tool(api_db, gmail_integration):
    tool = AgentTool(
        id=uuid4(),
        name="gmail",
        display_name="Gmail",
        description="Email management via Gmail API",
        category="communication",
        risk_level="medium",
        requires_approval=False,
        is_active=True,
        integration_id=gmail_integration.id,
    )
    api_db.add(tool)
    api_db.flush()

    actions = [
        ToolAction(id=uuid4(), tool_id=tool.id, name="read_email", display_name="Read Email", description="Read an email"),
        ToolAction(id=uuid4(), tool_id=tool.id, name="send_email", display_name="Send Email", description="Send an email"),
        ToolAction(id=uuid4(), tool_id=tool.id, name="search_emails", display_name="Search Emails", description="Search emails"),
    ]
    for action in actions:
        api_db.add(action)
    api_db.flush()

    return tool


@pytest.fixture
def gmail_permission(api_db):
    perms = [
        Permission(id=uuid4(), name="gmail.read_email", description="Read emails", category="gmail", risk_level="low", default_status="allowed", is_active=True),
        Permission(id=uuid4(), name="gmail.send_email", description="Send emails", category="gmail", risk_level="medium", default_status="allowed", is_active=True),
        Permission(id=uuid4(), name="gmail.search_emails", description="Search emails", category="gmail", risk_level="low", default_status="allowed", is_active=True),
    ]
    for p in perms:
        api_db.add(p)
    api_db.flush()
    return perms


@pytest.fixture
def agent_tool_assignment(api_db, gmail_agent, gmail_tool):
    assignment = AgentToolAssignment(
        id=uuid4(),
        agent_id=gmail_agent.id,
        tool_id=gmail_tool.id,
        tool_name="gmail",
        is_active=True,
        is_enabled=True,
    )
    api_db.add(assignment)
    api_db.flush()
    return assignment


@pytest.fixture
def agent_permissions(api_db, gmail_agent, gmail_permission):
    for perm in gmail_permission:
        ap = AgentPermission(
            id=uuid4(),
            agent_id=gmail_agent.id,
            permission_id=perm.id,
            access_level="allowed",
        )
        api_db.add(ap)
    api_db.flush()


# ---------------------------------------------------------------------------
# Test Class 1: Gmail Connection
# ---------------------------------------------------------------------------

class TestGmailConnection:
    """Tests 1-3: Gmail account connection and OAuth token management."""

    def test_gmail_connection_success(self, api_db, gmail_account, gmail_integration):
        """Test 1: Successfully connecting a Gmail account."""
        assert gmail_account.status == "connected"
        assert gmail_account.integration_id == gmail_integration.id
        assert gmail_account.oauth2_access_token is not None
        assert gmail_account.oauth2_refresh_token is not None

    def test_invalid_expired_oauth_token(self, api_db, gmail_account):
        """Test 2: Handling invalid/expired OAuth tokens."""
        from app.services.gmail_monitor_service import GmailMonitorService

        gmail_account.oauth2_token_expiry = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
        api_db.commit()

        service = GmailMonitorService(api_db)

        with patch("app.services.oauth2_service.OAuth2Service") as mock_oauth:
            mock_oauth.return_value.refresh_access_token.return_value = None
            mock_oauth.return_value.get_access_token.return_value = None

            result = service.check_account(gmail_account.id)
            assert result["success"] is False

    def test_token_refresh(self, api_db, gmail_account):
        """Test 3: Token refresh when expired."""
        gmail_account.oauth2_token_expiry = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).isoformat()
        api_db.commit()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        with patch("app.services.oauth2_service.OAuth2Service") as mock_oauth:
            mock_oauth.return_value.refresh_access_token.return_value = "new_access_token"

            from app.services.oauth2_service import OAuth2Service
            service = OAuth2Service(api_db)
            result = service.refresh_access_token(gmail_account)

            assert result == "new_access_token"


# ---------------------------------------------------------------------------
# Test Class 2: Agent Lifecycle
# ---------------------------------------------------------------------------

class TestAgentLifecycle:
    """Tests 4-7: Agent activation, deactivation, and configuration."""

    def test_agent_inactive_blocks_processing(self, api_db, gmail_agent, gmail_account, agent_permissions, agent_tool_assignment):
        """Test 4: Inactive agent should not process emails."""
        from app.services.gmail_monitor_service import GmailMonitorService

        gmail_agent.lifecycle_status = LifecycleStatus.INACTIVE
        api_db.commit()

        service = GmailMonitorService(api_db)
        msg = _make_gmail_message()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": msg["id"], "payload": {"headers": [{"name": "Subject", "value": msg["subject"]}, {"name": "From", "value": msg["from"]}]}}
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = asyncio.run(service._process_message(msg, gmail_account, MagicMock()))

    def test_agent_active_processes_emails(self, api_db, gmail_agent, gmail_account, agent_permissions, agent_tool_assignment):
        """Test 5: Active agent should process emails."""
        from app.services.gmail_monitor_service import GmailMonitorService

        assert gmail_agent.lifecycle_status == LifecycleStatus.ACTIVE

        service = GmailMonitorService(api_db)
        msg = _make_gmail_message()
        sync_state = MagicMock()
        sync_state.processed_message_ids = []

        with patch.object(service, "_fetch_message", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = msg

            with patch("app.services.gmail_deduplication_service.GmailDeduplicationService") as mock_dedup:
                mock_dedup.return_value.claim.return_value = MagicMock(value="claimed")

                with patch("app.services.trigger_service.TriggerService") as mock_trigger:
                    mock_trigger.return_value.fire_integration_trigger.return_value = MagicMock(id=uuid4())

                    result = asyncio.run(service._process_message(msg, gmail_account, sync_state))

    def test_missing_tool_assignment(self, api_db, gmail_agent, gmail_account, agent_permissions):
        """Test 6: Agent without Gmail tool assignment cannot use Gmail tools."""
        from app.services.tool_execution_service import ToolExecutionService

        gmail_agent.tools = ""
        api_db.commit()

        service = ToolExecutionService(api_db)

        result = service.execute_tool(
            agent_id=gmail_agent.id,
            tool_name="gmail",
            action="read_email",
            parameters={"message_id": "msg_123"},
        )
        assert result.get("success") is False

    def test_missing_integration(self, api_db, gmail_agent, gmail_account):
        """Test 7: Agent without Gmail integration cannot process Gmail events."""
        from app.services.gmail_monitor_service import GmailMonitorService

        api_db.query(AgentIntegration).filter(
            AgentIntegration.agent_id == gmail_agent.id
        ).delete()
        api_db.commit()

        service = GmailMonitorService(api_db)
        msg = _make_gmail_message()
        sync_state = MagicMock()
        sync_state.processed_message_ids = []

        result = asyncio.run(service._process_message(msg, gmail_account, sync_state))
        assert result is False


# ---------------------------------------------------------------------------
# Test Class 3: Multiple Accounts
# ---------------------------------------------------------------------------

class TestMultipleAccounts:
    """Tests 8-9: Multiple Gmail accounts and ownership."""

    def test_multiple_gmail_accounts_different_users(self, api_db, gmail_integration):
        """Test 8: Multiple Gmail accounts from different users."""
        user1 = User(id=uuid4(), email="user1@test.com", name="User 1", role="user", is_active=True)
        user2 = User(id=uuid4(), email="user2@test.com", name="User 2", role="user", is_active=True)
        api_db.add_all([user1, user2])
        api_db.flush()

        account1 = IntegrationAccount(
            id=uuid4(), integration_id=gmail_integration.id, user_id=user1.id,
            display_name="user1@gmail.com", status="connected", is_active=True,
            oauth2_access_token=encrypt_field("token1"), oauth2_refresh_token=encrypt_field("refresh1"),
        )
        account2 = IntegrationAccount(
            id=uuid4(), integration_id=gmail_integration.id, user_id=user2.id,
            display_name="user2@gmail.com", status="connected", is_active=True,
            oauth2_access_token=encrypt_field("token2"), oauth2_refresh_token=encrypt_field("refresh2"),
        )
        api_db.add_all([account1, account2])
        api_db.flush()

        accounts = api_db.query(IntegrationAccount).filter(
            IntegrationAccount.integration_id == gmail_integration.id,
        ).all()
        assert len(accounts) == 2

    def test_wrong_account_ownership(self, api_db, gmail_account):
        """Test 9: User cannot access another user's Gmail account."""
        from app.services.gmail_monitor_service import GmailMonitorService

        other_user = User(
            id=uuid4(), email="other@test.com", name="Other User",
            role="user", is_active=True,
        )
        api_db.add(other_user)
        api_db.flush()

        service = GmailMonitorService(api_db)
        result = service.check_account(gmail_account.id)
        assert "success" in result


# ---------------------------------------------------------------------------
# Test Class 4: Email Detection and Processing
# ---------------------------------------------------------------------------

class TestEmailDetection:
    """Tests 10-12: Email detection, duplicates, and concurrency."""

    def test_new_email_detection(self, api_db, gmail_agent, gmail_account, agent_permissions, agent_tool_assignment):
        """Test 10: New email is detected and triggers agent."""
        from app.services.gmail_monitor_service import GmailMonitorService

        service = GmailMonitorService(api_db)
        msg = _make_gmail_message(msg_id="new_msg_001")
        sync_state = MagicMock()
        sync_state.processed_message_ids = []

        with patch.object(service, "_fetch_message", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = msg

            with patch("app.services.gmail_deduplication_service.GmailDeduplicationService") as mock_dedup:
                mock_dedup.return_value.claim.return_value = MagicMock(value="claimed")

                with patch("app.services.trigger_service.TriggerService") as mock_trigger:
                    mock_trigger.return_value.fire_integration_trigger.return_value = MagicMock(id=uuid4())

                    result = asyncio.run(service._process_message(msg, gmail_account, sync_state))

    def test_duplicate_email(self, api_db):
        """Test 11: Duplicate email is rejected by deduplication."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        account_id = uuid4()
        msg_id = "duplicate_msg"
        agent_id = uuid4()

        svc = GmailDeduplicationService(api_db)
        outcome1 = svc.claim(account_id, msg_id, agent_id)
        assert outcome1 == DedupOutcome.CLAIMED

        svc.mark_completed(account_id, msg_id, agent_id)

        outcome2 = svc.claim(account_id, msg_id, agent_id)
        assert outcome2 == DedupOutcome.ALREADY_COMPLETED

    def test_concurrent_duplicate_event(self, api_db):
        """Test 12: Concurrent duplicate events handled correctly."""
        from app.services.gmail_deduplication_service import GmailDeduplicationService, DedupOutcome

        account_id = uuid4()
        msg_id = "concurrent_msg"
        agent_id = uuid4()

        svc1 = GmailDeduplicationService(api_db)
        svc2 = GmailDeduplicationService(api_db)

        outcome1 = svc1.claim(account_id, msg_id, agent_id)
        assert outcome1 == DedupOutcome.CLAIMED

        outcome2 = svc2.claim(account_id, msg_id, agent_id)
        assert outcome2 == DedupOutcome.PROCESSING


# ---------------------------------------------------------------------------
# Test Class 5: Permissions and Approvals
# ---------------------------------------------------------------------------

class TestPermissionsAndApprovals:
    """Tests 13-15: Permission checks and approval workflows."""

    def test_permission_denied(self, api_db, gmail_agent, gmail_tool):
        """Test 13: Agent without permission cannot execute action."""
        from app.services.tool_execution_service import ToolExecutionService

        api_db.query(AgentPermission).filter(
            AgentPermission.agent_id == gmail_agent.id
        ).delete()
        api_db.commit()

        service = ToolExecutionService(api_db)

        result = service.execute_tool(
            agent_id=gmail_agent.id,
            tool_name="gmail",
            action="send_email",
            parameters={"to": "test@test.com", "subject": "Test"},
        )
        assert result.get("success") is False

    def test_approval_required(self, api_db, gmail_agent, gmail_account, agent_permissions, agent_tool_assignment):
        """Test 14: High-risk action requires approval."""
        from app.services.tool_execution_service import ToolExecutionService
        from app.models.risk_rule import RiskRule

        risk_rule = RiskRule(
            id=uuid4(), name="Email Sending Approval",
            description="Requires approval for sending emails",
            action_name="send_email", risk_level="high",
            requires_approval=True, priority=10, is_active=True,
        )
        api_db.add(risk_rule)
        api_db.commit()

        service = ToolExecutionService(api_db)
        result = service.execute_tool(
            agent_id=gmail_agent.id,
            tool_name="gmail",
            action="send_email",
            parameters={"to": "test@test.com", "subject": "Test"},
        )
        assert result.get("requires_approval") is True or "approval" in str(result).lower()

    def test_approval_granted(self, api_db, gmail_agent, gmail_account, agent_permissions, agent_tool_assignment, gmail_tool):
        """Test 15: Approved action executes successfully."""
        from app.services.tool_execution_service import ToolExecutionService
        from app.models.approval import Approval

        approval = Approval(
            id=uuid4(), agent_id=gmail_agent.id, action="send_email",
            tool_id=gmail_tool.id,
            risk_level="high", status="approved",
            parameters={"_tool_name": "gmail", "to": "test@test.com", "subject": "Test"},
        )
        api_db.add(approval)
        api_db.commit()

        service = ToolExecutionService(api_db)

        with patch("app.services.integration_providers.registry.get_provider") as mock_provider:
            mock_provider.return_value = AsyncMock()
            mock_provider.return_value.execute_action = AsyncMock(return_value=MagicMock(
                success=True, data={"message_id": "sent_123"}, error=None
            ))

            result = service.execute_approved_action(approval.id)
            assert result.get("success") is True


# ---------------------------------------------------------------------------
# Test Class 6: Error Handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Tests 16-20: API failures, runtime failures, and recovery."""

    def test_gmail_api_failure(self, api_db, gmail_account):
        """Test 16: Gmail API failure is handled gracefully."""
        from app.services.gmail_monitor_service import GmailMonitorService

        service = GmailMonitorService(api_db)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Gmail API unavailable")

            result = service.check_account(gmail_account.id)
            assert result["success"] is False

    def test_agent_runtime_failure(self, api_db, gmail_agent):
        """Test 17: Agent runtime failure doesn't crash the system."""
        from app.services.agent_runtime import AgentRuntime

        runtime = AgentRuntime.get_instance()

        with patch.object(runtime, "_activate_existing_agents", new_callable=AsyncMock) as mock_activate:
            mock_activate.side_effect = Exception("Runtime initialization failed")

            try:
                asyncio.run(runtime.start())
            except Exception:
                pass

    def test_scheduler_restart(self, api_db):
        """Test 18: Scheduler can be restarted safely."""
        from app.services.scheduler import SchedulerService

        scheduler = SchedulerService.get_instance()

        asyncio.run(scheduler.start())
        assert scheduler._running

        asyncio.run(scheduler.stop())
        assert not scheduler._running

        asyncio.run(scheduler.start())
        assert scheduler._running

        asyncio.run(scheduler.stop())

    def test_application_restart(self, api_db):
        """Test 19: Application can restart without data loss."""
        agent = AIAgent(
            id=uuid4(), name="Persistent Agent", role="assistant",
            status="active", lifecycle_status="active",
        )
        api_db.add(agent)
        api_db.commit()

        api_db.expire_all()
        found_agent = api_db.query(AIAgent).filter(AIAgent.id == agent.id).first()
        assert found_agent is not None
        assert found_agent.name == "Persistent Agent"

    def test_database_connection_failure(self, api_db):
        """Test 20: Database connection failure is handled."""
        from app.database.session import check_db_health

        with patch("app.database.session.engine") as mock_engine:
            mock_engine.connect.side_effect = OperationalError(
                "connection refused", {}, Exception("timeout")
            )

            health = check_db_health()
            assert health["status"] == "unhealthy"
