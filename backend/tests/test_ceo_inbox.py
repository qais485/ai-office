"""Tests for CEO Inbox: aggregated items, filtering, bulk actions."""
import pytest
from uuid import uuid4

from app.services.ceo_inbox_service import CEOInboxService
from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.task import Task, TaskStatus, TaskPriority, TaskType
from app.models.approval import Approval
from app.models.notification import Notification


class TestCEOInboxItems:
    """Get inbox items returns list."""

    def test_get_inbox_items_returns_list(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_inbox_items_contain_required_fields(self, api_db, sample_agent, sample_approval, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            item = data[0]
            assert "type" in item
            assert "id" in item
            assert "title" in item
            assert "message" in item
            assert "priority" in item

    def test_inbox_includes_pending_approvals(self, api_db, sample_agent, sample_approval, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/?filter_type=approval")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for item in data:
            assert item["type"] == "approval"

    def test_inbox_includes_notifications(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/?filter_type=notification")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for item in data:
            assert item["type"] == "notification"

    def test_inbox_includes_error_agents(self, api_db, ceo_headers, client):
        agent = AIAgent(
            id=uuid4(),
            name="Error Agent",
            role="assistant",
            status=AgentStatus.ACTIVE,
            lifecycle_status=LifecycleStatus.ERROR,
            last_error="Connection timeout",
        )
        api_db.add(agent)
        api_db.commit()

        response = client.get("/api/v1/ceo/inbox/?filter_type=agent_error")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(item["type"] == "agent_error" for item in data)

    def test_inbox_includes_failed_tasks(self, api_db, sample_agent, ceo_headers, client):
        task = Task(
            id=uuid4(),
            title="Failed Task",
            description="This task failed",
            status=TaskStatus.FAILED,
            task_type=TaskType.GENERAL,
            agent_id=sample_agent.id,
            priority=TaskPriority.MEDIUM,
            error_message="Timeout exceeded",
        )
        api_db.add(task)
        api_db.commit()

        response = client.get("/api/v1/ceo/inbox/?filter_type=failed_task")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(item["type"] == "failed_task" for item in data)

    def test_inbox_includes_high_priority_pending_tasks(self, api_db, sample_agent, ceo_headers, client):
        task = Task(
            id=uuid4(),
            title="Urgent Task",
            description="Needs immediate attention",
            status=TaskStatus.PENDING,
            task_type=TaskType.GENERAL,
            agent_id=sample_agent.id,
            priority=TaskPriority.URGENT,
        )
        api_db.add(task)
        api_db.commit()

        response = client.get("/api/v1/ceo/inbox/?filter_type=pending_task")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(item["type"] == "pending_task" for item in data)

    def test_inbox_service_returns_items(self, api_db, sample_agent, sample_notification):
        service = CEOInboxService(api_db)
        user_id = sample_notification.user_id
        items = service.get_inbox_items(user_id)
        assert isinstance(items, list)

    def test_inbox_items_sorted_by_priority(self, api_db, sample_agent, sample_approval, sample_notification):
        service = CEOInboxService(api_db)
        user_id = sample_notification.user_id
        items = service.get_inbox_items(user_id)
        if len(items) > 1:
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for i in range(len(items) - 1):
                p1 = priority_order.get(items[i].get("priority", "low"), 3)
                p2 = priority_order.get(items[i + 1].get("priority", "low"), 3)
                assert p1 <= p2

    def test_unauthenticated_returns_401(self, client):
        response = client.get("/api/v1/ceo/inbox/")
        assert response.status_code in (401, 403)


class TestCEOInboxCounts:
    """Get unread/total counts."""

    def test_get_inbox_counts_returns_dict(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/counts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "total" in data

    def test_counts_include_pending_approvals(self, api_db, sample_agent, sample_approval, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/counts")
        assert response.status_code == 200
        data = response.json()
        assert "pending_approvals" in data
        assert data["pending_approvals"] >= 1

    def test_counts_include_unread_notifications(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/counts")
        assert response.status_code == 200
        data = response.json()
        assert "unread_notifications" in data
        assert data["unread_notifications"] >= 1

    def test_counts_include_error_agents(self, api_db, ceo_headers, client):
        agent = AIAgent(
            id=uuid4(),
            name="Error Agent",
            role="assistant",
            status=AgentStatus.ACTIVE,
            lifecycle_status=LifecycleStatus.ERROR,
            last_error="Crash",
        )
        api_db.add(agent)
        api_db.commit()

        response = client.get("/api/v1/ceo/inbox/counts")
        assert response.status_code == 200
        data = response.json()
        assert "error_agents" in data
        assert data["error_agents"] >= 1

    def test_counts_include_failed_tasks(self, api_db, sample_agent, ceo_headers, client):
        task = Task(
            id=uuid4(),
            title="Failed Task",
            status=TaskStatus.FAILED,
            task_type=TaskType.GENERAL,
            agent_id=sample_agent.id,
            priority=TaskPriority.MEDIUM,
        )
        api_db.add(task)
        api_db.commit()

        response = client.get("/api/v1/ceo/inbox/counts")
        assert response.status_code == 200
        data = response.json()
        assert "failed_tasks" in data
        assert data["failed_tasks"] >= 1

    def test_total_equals_sum_of_parts(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/counts")
        assert response.status_code == 200
        data = response.json()
        expected_total = (
            data["pending_approvals"]
            + data["error_agents"]
            + data["failed_tasks"]
            + data["unread_notifications"]
            + data["system_alerts"]
        )
        assert data["total"] == expected_total

    def test_counts_service_method(self, api_db, sample_agent, sample_notification):
        service = CEOInboxService(api_db)
        counts = service.get_inbox_counts(sample_notification.user_id)
        assert isinstance(counts, dict)
        assert "total" in counts
        assert "pending_approvals" in counts
        assert "unread_notifications" in counts


class TestCEOInboxFiltering:
    """Filter by type and priority."""

    def test_filter_by_type_approval(self, api_db, sample_agent, sample_approval, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/?filter_type=approval")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["type"] == "approval"

    def test_filter_by_type_notification(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/?filter_type=notification")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["type"] == "notification"

    def test_filter_by_type_agent_error(self, api_db, ceo_headers, client):
        agent = AIAgent(
            id=uuid4(),
            name="Error Agent",
            role="assistant",
            status=AgentStatus.ACTIVE,
            lifecycle_status=LifecycleStatus.ERROR,
            last_error="DB connection lost",
        )
        api_db.add(agent)
        api_db.commit()

        response = client.get("/api/v1/ceo/inbox/?filter_type=agent_error")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["type"] == "agent_error"

    def test_filter_by_type_failed_task(self, api_db, sample_agent, ceo_headers, client):
        task = Task(
            id=uuid4(),
            title="Failed Task",
            status=TaskStatus.FAILED,
            task_type=TaskType.GENERAL,
            agent_id=sample_agent.id,
            priority=TaskPriority.MEDIUM,
        )
        api_db.add(task)
        api_db.commit()

        response = client.get("/api/v1/ceo/inbox/?filter_type=failed_task")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["type"] == "failed_task"

    def test_filter_by_priority_high(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/?filter_priority=high")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["priority"] == "high"

    def test_filter_by_priority_medium(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/?filter_priority=medium")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["priority"] == "medium"

    def test_filter_by_priority_low(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/?filter_priority=low")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["priority"] == "low"

    def test_filter_combined_type_and_priority(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/?filter_type=notification&filter_priority=low")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["type"] == "notification"
            assert item["priority"] == "low"

    def test_unread_only_filter(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.get("/api/v1/ceo/inbox/?unread_only=true")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_filter_service_method(self, api_db, sample_agent, sample_notification):
        service = CEOInboxService(api_db)
        user_id = sample_notification.user_id
        filtered = service.get_inbox_items(user_id, filter_type="notification")
        for item in filtered:
            assert item["type"] == "notification"

    def test_filter_priority_service_method(self, api_db, sample_agent, sample_notification):
        service = CEOInboxService(api_db)
        user_id = sample_notification.user_id
        filtered = service.get_inbox_items(user_id, filter_priority="low")
        for item in filtered:
            assert item["priority"] == "low"


class TestCEOInboxMarkRead:
    """Mark items as read."""

    def test_mark_notification_read(self, api_db, sample_notification, ceo_headers, client):
        notification_id = sample_notification.id
        response = client.post(f"/api/v1/ceo/inbox/{notification_id}/read")
        assert response.status_code == 200
        assert response.json()["message"] == "Notification marked as read"

    def test_mark_nonexistent_notification_returns_404(self, api_db, ceo_headers, client):
        fake_id = uuid4()
        response = client.post(f"/api/v1/ceo/inbox/{fake_id}/read")
        assert response.status_code == 404

    def test_mark_all_notifications_read(self, api_db, sample_agent, sample_notification, ceo_headers, client):
        response = client.post("/api/v1/ceo/inbox/read-all")
        assert response.status_code == 200
        data = response.json()
        assert "marked" in data
        assert isinstance(data["marked"], int)

    def test_mark_all_read_sets_is_read_true(self, api_db, sample_notification):
        service = CEOInboxService(api_db)
        user_id = sample_notification.user_id
        assert sample_notification.is_read is False

        count = service.mark_all_notifications_read(user_id)
        assert count >= 1

        api_db.refresh(sample_notification)
        assert sample_notification.is_read is True

    def test_mark_single_read_via_service(self, api_db, sample_notification):
        service = CEOInboxService(api_db)
        assert sample_notification.is_read is False

        result = service.mark_notification_read(sample_notification.id)
        assert result is True

        api_db.refresh(sample_notification)
        assert sample_notification.is_read is True

    def test_mark_nonexistent_read_via_service(self, api_db):
        service = CEOInboxService(api_db)
        result = service.mark_notification_read(uuid4())
        assert result is False

    def test_dismiss_notification(self, api_db, sample_notification, ceo_headers, client):
        notification_id = sample_notification.id
        response = client.post(f"/api/v1/ceo/inbox/notification/{notification_id}/dismiss")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_archive_notification(self, api_db, sample_notification, ceo_headers, client):
        notification_id = sample_notification.id
        response = client.post(f"/api/v1/ceo/inbox/notification/{notification_id}/archive")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_resolve_notification(self, api_db, sample_notification, ceo_headers, client):
        notification_id = sample_notification.id
        response = client.post(f"/api/v1/ceo/inbox/notification/{notification_id}/resolve")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_approve_approval_item(self, api_db, sample_agent, sample_approval, ceo_headers, client):
        approval_id = sample_approval.id
        response = client.post(
            f"/api/v1/ceo/inbox/approval/{approval_id}/approve",
            json={"notes": "Approved by test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_reject_approval_item(self, api_db, sample_agent, sample_approval, ceo_headers, client):
        approval_id = sample_approval.id
        response = client.post(
            f"/api/v1/ceo/inbox/approval/{approval_id}/reject",
            json={"notes": "Rejected by test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_mark_all_read_returns_zero_when_none_unread(self, api_db, sample_notification):
        service = CEOInboxService(api_db)
        user_id = sample_notification.user_id
        service.mark_all_notifications_read(user_id)
        count = service.mark_all_notifications_read(user_id)
        assert count == 0
