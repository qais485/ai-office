"""Tests for Audit Log: creation, filtering, retrieval."""
import pytest
from uuid import uuid4

from app.services.audit_service import AuditService
from app.schemas.audit_log import AuditLogCreate
from app.models.audit_log import AuditLog


class TestAuditLogCreation:
    """Create audit log entries via service."""

    def test_log_action_creates_entry(self, api_db):
        service = AuditService(api_db)
        log = service.log_action(
            action="user.login",
            user_id=uuid4(),
            details={"method": "password"},
            ip_address="127.0.0.1",
        )
        assert log is not None
        assert log.id is not None
        assert log.action == "user.login"

    def test_log_action_stores_all_fields(self, api_db):
        user_id = uuid4()
        agent_id = uuid4()
        resource_id = uuid4()

        service = AuditService(api_db)
        log = service.log_action(
            action="agent.execute_task",
            user_id=user_id,
            agent_id=agent_id,
            resource_type="task",
            resource_id=resource_id,
            details={"task_name": "Generate report"},
            ip_address="10.0.0.1",
        )

        assert log.user_id == user_id
        assert log.agent_id == agent_id
        assert log.resource_type == "task"
        assert log.resource_id == resource_id
        assert log.details == {"task_name": "Generate report"}
        assert log.ip_address == "10.0.0.1"

    def test_log_action_with_none_optional_fields(self, api_db):
        service = AuditService(api_db)
        log = service.log_action(action="system.startup")
        assert log.action == "system.startup"
        assert log.user_id is None
        assert log.agent_id is None
        assert log.resource_type is None
        assert log.resource_id is None
        assert log.details is None
        assert log.ip_address is None

    def test_log_method_with_schema(self, api_db):
        service = AuditService(api_db)
        data = AuditLogCreate(
            action="user.logout",
            user_id=uuid4(),
            details={"session_id": "abc123"},
        )
        log = service.log(data)
        assert log.action == "user.logout"
        assert log.user_id == data.user_id
        assert log.details == {"session_id": "abc123"}

    def test_multiple_logs_created(self, api_db):
        service = AuditService(api_db)
        for i in range(5):
            service.log_action(action=f"test.action.{i}", user_id=uuid4())

        logs = service.get_logs()
        assert len(logs) == 5

    def test_log_has_timestamp(self, api_db):
        service = AuditService(api_db)
        log = service.log_action(action="test.timestamp")
        assert log.created_at is not None


class TestAuditLogFiltering:
    """Filter by user_id, agent_id, resource_type."""

    def test_filter_by_user_id(self, api_db):
        user_id = uuid4()
        other_user_id = uuid4()

        service = AuditService(api_db)
        service.log_action(action="user.action_a", user_id=user_id)
        service.log_action(action="user.action_b", user_id=other_user_id)
        service.log_action(action="user.action_c", user_id=user_id)

        logs = service.get_logs(user_id=user_id)
        assert len(logs) == 2
        for log in logs:
            assert log.user_id == user_id

    def test_filter_by_agent_id(self, api_db):
        agent_id = uuid4()
        other_agent_id = uuid4()

        service = AuditService(api_db)
        service.log_action(action="agent.action_a", agent_id=agent_id)
        service.log_action(action="agent.action_b", agent_id=other_agent_id)
        service.log_action(action="agent.action_c", agent_id=agent_id)

        logs = service.get_logs(agent_id=agent_id)
        assert len(logs) == 2
        for log in logs:
            assert log.agent_id == agent_id

    def test_filter_by_resource_type(self, api_db):
        service = AuditService(api_db)
        service.log_action(action="create", resource_type="task")
        service.log_action(action="create", resource_type="agent")
        service.log_action(action="update", resource_type="task")

        logs = service.get_logs(resource_type="task")
        assert len(logs) == 2
        for log in logs:
            assert log.resource_type == "task"

    def test_filter_combined_user_and_agent(self, api_db):
        user_id = uuid4()
        agent_id = uuid4()

        service = AuditService(api_db)
        service.log_action(action="a", user_id=user_id, agent_id=agent_id)
        service.log_action(action="b", user_id=user_id, agent_id=uuid4())
        service.log_action(action="c", user_id=uuid4(), agent_id=agent_id)

        logs = service.get_logs(user_id=user_id, agent_id=agent_id)
        assert len(logs) == 1
        assert logs[0].user_id == user_id
        assert logs[0].agent_id == agent_id

    def test_filter_with_limit(self, api_db):
        service = AuditService(api_db)
        for i in range(10):
            service.log_action(action=f"action.{i}", user_id=uuid4())

        logs = service.get_logs(limit=5)
        assert len(logs) == 5

    def test_filter_no_results(self, api_db):
        service = AuditService(api_db)
        logs = service.get_logs(user_id=uuid4())
        assert len(logs) == 0

    def test_filter_returns_ordered_by_created_at_desc(self, api_db):
        service = AuditService(api_db)
        service.log_action(action="first", user_id=uuid4())
        service.log_action(action="second", user_id=uuid4())
        service.log_action(action="third", user_id=uuid4())

        logs = service.get_logs()
        assert len(logs) == 3
        assert logs[0].created_at >= logs[1].created_at
        assert logs[1].created_at >= logs[2].created_at


class TestAuditLogRetrieval:
    """Get single log entry."""

    def test_get_log_by_id(self, api_db, sample_audit_log):
        service = AuditService(api_db)
        log = service.get_log(sample_audit_log.id)
        assert log is not None
        assert log.id == sample_audit_log.id
        assert log.action == sample_audit_log.action

    def test_get_nonexistent_log_returns_none(self, api_db):
        service = AuditService(api_db)
        log = service.get_log(uuid4())
        assert log is None

    def test_get_log_preserves_details(self, api_db):
        service = AuditService(api_db)
        original_details = {"key": "value", "nested": {"a": 1}}
        created = service.log_action(
            action="test.details",
            details=original_details,
        )

        retrieved = service.get_log(created.id)
        assert retrieved is not None
        assert retrieved.details == original_details

    def test_get_log_via_api(self, api_db, sample_audit_log, ceo_headers, client):
        log_id = sample_audit_log.id
        response = client.get(f"/api/v1/audit/{log_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(log_id)
        assert "action" in data
        assert "created_at" in data

    def test_get_nonexistent_log_via_api_returns_404(self, api_db, ceo_headers, client):
        fake_id = uuid4()
        response = client.get(f"/api/v1/audit/{fake_id}")
        assert response.status_code == 404

    def test_log_response_has_correct_schema(self, api_db, sample_audit_log, ceo_headers, client):
        log_id = sample_audit_log.id
        response = client.get(f"/api/v1/audit/{log_id}")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "action" in data
        assert "resource_type" in data
        assert "resource_id" in data
        assert "details" in data
        assert "ip_address" in data
        assert "user_id" in data
        assert "agent_id" in data
        assert "created_at" in data


class TestAuditAPI:
    """GET /api/v1/audit/ returns logs."""

    def test_get_audit_logs_returns_list(self, api_db, sample_audit_log, ceo_headers, client):
        response = client.get("/api/v1/audit/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_audit_logs_contains_sample(self, api_db, sample_audit_log, ceo_headers, client):
        response = client.get("/api/v1/audit/")
        assert response.status_code == 200
        data = response.json()
        log_ids = [item["id"] for item in data]
        assert str(sample_audit_log.id) in log_ids

    def test_get_audit_logs_filter_by_user_id(self, api_db, ceo_headers, client):
        user_id = uuid4()
        service = AuditService(api_db)
        service.log_action(action="test.user", user_id=user_id)
        service.log_action(action="test.other", user_id=uuid4())

        response = client.get(f"/api/v1/audit/?user_id={user_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert item["user_id"] == str(user_id)

    def test_get_audit_logs_filter_by_agent_id(self, api_db, ceo_headers, client):
        agent_id = uuid4()
        service = AuditService(api_db)
        service.log_action(action="test.agent", agent_id=agent_id)
        service.log_action(action="test.other", agent_id=uuid4())

        response = client.get(f"/api/v1/audit/?agent_id={agent_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert item["agent_id"] == str(agent_id)

    def test_get_audit_logs_filter_by_resource_type(self, api_db, ceo_headers, client):
        service = AuditService(api_db)
        service.log_action(action="create", resource_type="task")
        service.log_action(action="create", resource_type="agent")

        response = client.get("/api/v1/audit/?resource_type=task")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert item["resource_type"] == "task"

    def test_get_audit_logs_with_limit(self, api_db, ceo_headers, client):
        service = AuditService(api_db)
        for i in range(10):
            service.log_action(action=f"action.{i}", user_id=uuid4())

        response = client.get("/api/v1/audit/?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3

    def test_get_audit_logs_default_limit(self, api_db, ceo_headers, client):
        response = client.get("/api/v1/audit/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_audit_logs_returns_ordered(self, api_db, ceo_headers, client):
        service = AuditService(api_db)
        service.log_action(action="first", user_id=uuid4())
        service.log_action(action="second", user_id=uuid4())

        response = client.get("/api/v1/audit/")
        assert response.status_code == 200
        data = response.json()
        if len(data) >= 2:
            from datetime import datetime
            for i in range(len(data) - 1):
                t1 = datetime.fromisoformat(data[i]["created_at"].replace("Z", "+00:00")) if "T" in data[i]["created_at"] else datetime.fromisoformat(data[i]["created_at"])
                t2 = datetime.fromisoformat(data[i + 1]["created_at"].replace("Z", "+00:00")) if "T" in data[i + 1]["created_at"] else datetime.fromisoformat(data[i + 1]["created_at"])
                assert t1 >= t2

    def test_unauthenticated_returns_401(self, client):
        response = client.get("/api/v1/audit/")
        assert response.status_code in (401, 403)
