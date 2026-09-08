"""Cross-account isolation contract tests.

The reported bug: one user's agents/rooms/tasks appeared in another user's
dashboard. These tests pin the fix — every account sees ONLY its own data,
and cross-account decisions are impossible.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.models.user import User
from app.models.agent import AIAgent
from app.models.room import OfficeRoom
from app.models.task import Task, TaskStatus
from app.models.approval import Approval
from app.utils.security import create_access_token


def _headers(user) -> dict:
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _make_user(api_db, email: str) -> User:
    user = User(id=uuid4(), email=email, name=email.split("@")[0], role="user", is_active=True)
    api_db.add(user)
    api_db.flush()
    return user


def _make_agent(api_db, user: User, name: str) -> AIAgent:
    agent = AIAgent(id=uuid4(), user_id=user.id, name=name, role="assistant",
                    description="iso agent", status="inactive",
                    lifecycle_status="active")
    api_db.add(agent)
    api_db.flush()
    return agent


@pytest.fixture
def account_a(api_db):
    return _make_user(api_db, "a@iso.test")


@pytest.fixture
def account_b(api_db):
    return _make_user(api_db, "b@iso.test")


class TestDashboardIsolation:
    def test_b_does_not_see_a_agent_count(self, client, api_db, account_a, account_b):
        _make_agent(api_db, account_a, "A-agent")
        api_db.flush()
        resp = client.get("/api/v1/ceo/dashboard/summary", headers=_headers(account_b))
        assert resp.status_code == 200
        assert resp.json()["agents"]["total"] == 0

    def test_a_sees_own_agent_count(self, client, api_db, account_a, account_b):
        _make_agent(api_db, account_a, "A-agent")
        api_db.flush()
        resp = client.get("/api/v1/ceo/dashboard/summary", headers=_headers(account_a))
        assert resp.status_code == 200
        assert resp.json()["agents"]["total"] == 1

    def test_room_counts_isolated(self, client, api_db, account_a, account_b):
        room = OfficeRoom(id=uuid4(), user_id=account_a.id, name="A-room",
                          room_type="office", status="available")
        api_db.add(room)
        api_db.flush()
        resp = client.get("/api/v1/ceo/dashboard/summary", headers=_headers(account_b))
        assert resp.status_code == 200
        assert resp.json()["rooms"]["total"] == 0

    def test_dashboard_summary_isolated(self, client, api_db, account_a, account_b):
        agent = _make_agent(api_db, account_a, "A-agent")
        api_db.add(Task(id=uuid4(), agent_id=agent.id, title="t",
                        description="d", status=TaskStatus.PENDING))
        api_db.flush()
        resp = client.get("/api/v1/dashboard/summary", headers=_headers(account_b))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agents"] == 0
        assert data["total_tasks"] == 0


class TestTaskStatsIsolation:
    def test_task_stats_scoped(self, client, api_db, account_a, account_b):
        agent = _make_agent(api_db, account_a, "A-agent")
        api_db.add(Task(id=uuid4(), agent_id=agent.id, title="t",
                        description="d", status=TaskStatus.COMPLETED))
        api_db.flush()
        resp = client.get("/api/v1/tasks/stats/summary", headers=_headers(account_b))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

        resp = client.get("/api/v1/tasks/stats/summary", headers=_headers(account_a))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


class TestApprovalIsolation:
    def test_b_cannot_decide_a_approval(self, client, api_db, account_a, account_b):
        agent = _make_agent(api_db, account_a, "A-agent")
        approval = Approval(
            id=uuid4(), agent_id=agent.id, action="send_email",
            risk_level="high", status="pending",
            parameters={}, reason="r", requested_at=datetime.now(timezone.utc).isoformat(),
        )
        api_db.add(approval)
        api_db.commit()

        resp = client.post(f"/api/v1/approvals/{approval.id}/approve",
                           json={"notes": "ok"}, headers=_headers(account_b))
        assert resp.status_code in (403, 404)

        api_db.refresh(approval)
        assert approval.status == "pending"

    def test_owner_can_decide_own_approval(self, client, api_db, account_a, account_b):
        agent = _make_agent(api_db, account_a, "A-agent")
        approval = Approval(
            id=uuid4(), agent_id=agent.id, action="send_email",
            risk_level="low", status="pending",
            parameters={}, reason="r", requested_at=datetime.now(timezone.utc).isoformat(),
        )
        api_db.add(approval)
        api_db.commit()

        resp = client.post(f"/api/v1/approvals/{approval.id}/approve",
                           json={"notes": "ok"}, headers=_headers(account_a))
        assert resp.status_code == 200

    def test_b_list_does_not_include_a_approvals(self, client, api_db, account_a, account_b):
        agent = _make_agent(api_db, account_a, "A-agent")
        api_db.add(Approval(
            id=uuid4(), agent_id=agent.id, action="send_email",
            risk_level="medium", status="pending",
            parameters={}, reason="r", requested_at=datetime.now(timezone.utc).isoformat(),
        ))
        api_db.flush()
        resp = client.get("/api/v1/approvals/", headers=_headers(account_b))
        assert resp.status_code == 200
        assert len(resp.json()) == 0


class TestAnalyticsIsolation:
    def test_company_analytics_scoped(self, client, api_db, account_a, account_b):
        _make_agent(api_db, account_a, "A-agent")
        api_db.flush()
        resp = client.get("/api/v1/analytics/company", headers=_headers(account_b))
        assert resp.status_code == 200
        assert resp.json()["total_agents"] == 0

    def test_ranking_scoped(self, client, api_db, account_a, account_b):
        _make_agent(api_db, account_a, "A-agent")
        api_db.flush()
        resp = client.get("/api/v1/analytics/ranking", headers=_headers(account_b))
        assert resp.status_code == 200
        assert resp.json() == []


class TestAgentListIsolation:
    def test_agent_list_scoped(self, client, api_db, account_a, account_b):
        _make_agent(api_db, account_a, "A-agent")
        api_db.flush()
        resp = client.get("/api/v1/agents/", headers=_headers(account_b))
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()]
        assert "A-agent" not in names


class TestUsersEndpointsRemoved:
    def test_users_list_endpoint_gone(self, client, regular_user):
        resp = client.get("/api/v1/users/", headers=_headers(regular_user))
        assert resp.status_code in (404, 405)

    def test_role_update_endpoint_gone(self, client, regular_user):
        resp = client.put(f"/api/v1/users/{regular_user.id}/role",
                          json={"role": "admin"}, headers=_headers(regular_user))
        assert resp.status_code in (404, 405)
