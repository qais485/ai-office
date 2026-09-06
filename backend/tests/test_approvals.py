import pytest
from uuid import uuid4

from app.models.approval import Approval
from app.models.approval_event import ApprovalEvent


class TestApprovalCRUD:
    def test_create_approval(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
            "parameters": {"to": "test@example.com", "subject": "Hello"},
        }
        response = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "send_email"
        assert data["risk_level"] == "medium"
        assert data["status"] == "pending"
        assert data["agent_id"] == str(sample_agent.id)

    def test_list_approvals_empty(self, client, ceo_headers):
        response = client.get("/api/v1/approvals/", headers=ceo_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_approvals_after_create(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "deploy_code",
            "risk_level": "high",
        }
        client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)

        response = client.get("/api/v1/approvals/", headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["action"] == "deploy_code"

    def test_create_approval_returns_401_without_auth(self, client, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "low",
        }
        response = client.post("/api/v1/approvals/", json=payload)
        assert response.status_code == 401

    def test_create_approval_with_all_fields(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "create_invoice",
            "risk_level": "critical",
            "parameters": {"amount": 5000, "currency": "USD"},
            "reason": "Client requested invoice",
        }
        response = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["parameters"]["amount"] == 5000
        assert data["reason"] == "Client requested invoice"


class TestApprovalApprove:
    def test_ceo_can_approve(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            params={"notes": "Looks good"},
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["decision_notes"] == "Looks good"

    def test_non_ceo_gets_403(self, client, user_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=user_headers)
        approval_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers=user_headers,
        )
        assert response.status_code == 403

    def test_admin_gets_403(self, client, admin_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=admin_headers)
        approval_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers=admin_headers,
        )
        assert response.status_code == 403

    def test_approve_nonexistent_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/approvals/{fake_id}/approve",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_approve_already_approved_returns_404(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        client.post(f"/api/v1/approvals/{approval_id}/approve", headers=ceo_headers)
        response = client.post(f"/api/v1/approvals/{approval_id}/approve", headers=ceo_headers)
        assert response.status_code == 404


class TestApprovalReject:
    def test_ceo_can_reject(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "delete_database",
            "risk_level": "critical",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            params={"notes": "Too risky"},
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["decision_notes"] == "Too risky"

    def test_non_ceo_cannot_reject(self, client, user_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "delete_database",
            "risk_level": "critical",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=user_headers)
        approval_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=user_headers,
        )
        assert response.status_code == 403

    def test_reject_nonexistent_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/approvals/{fake_id}/reject",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_reject_already_rejected_returns_404(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "delete_database",
            "risk_level": "critical",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        client.post(f"/api/v1/approvals/{approval_id}/reject", headers=ceo_headers)
        response = client.post(f"/api/v1/approvals/{approval_id}/reject", headers=ceo_headers)
        assert response.status_code == 404


class TestApprovalCancel:
    def test_creator_can_cancel(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "low",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/approvals/{approval_id}/cancel",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_cancel_nonexistent_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/approvals/{fake_id}/cancel",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_cancel_already_approved_returns_404(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "low",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        client.post(f"/api/v1/approvals/{approval_id}/approve", headers=ceo_headers)
        response = client.post(
            f"/api/v1/approvals/{approval_id}/cancel",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_regular_user_can_cancel(self, client, user_headers, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "low",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=user_headers)
        approval_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/approvals/{approval_id}/cancel",
            headers=user_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"


class TestApprovalRetry:
    def test_retry_rejected_approval(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        client.post(f"/api/v1/approvals/{approval_id}/reject", headers=ceo_headers)

        response = client.post(
            f"/api/v1/approvals/{approval_id}/retry",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["retry_count"] == 1

    def test_retry_pending_returns_unchanged(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        response = client.post(
            f"/api/v1/approvals/{approval_id}/retry",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["retry_count"] == 0

    def test_retry_nonexistent_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/approvals/{fake_id}/retry",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_retry_approved_returns_unchanged(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        client.post(f"/api/v1/approvals/{approval_id}/approve", headers=ceo_headers)
        response = client.post(
            f"/api/v1/approvals/{approval_id}/retry",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["retry_count"] == 0


class TestApprovalStats:
    def test_stats_empty(self, client, ceo_headers):
        response = client.get("/api/v1/approvals/stats", headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["pending"] == 0
        assert data["approved"] == 0
        assert data["rejected"] == 0
        assert data["expired"] == 0
        assert data["cancelled"] == 0
        assert data["total"] == 0

    def test_stats_with_approvals(self, client, ceo_headers, sample_agent):
        actions = [
            ("send_email", "pending"),
            ("deploy_code", "pending"),
            ("send_email", "approved"),
            ("delete_record", "rejected"),
        ]
        for action, status in actions:
            payload = {
                "agent_id": str(sample_agent.id),
                "action": action,
                "risk_level": "medium",
            }
            create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
            aid = create_resp.json()["id"]
            if status == "approved":
                client.post(f"/api/v1/approvals/{aid}/approve", headers=ceo_headers)
            elif status == "rejected":
                client.post(f"/api/v1/approvals/{aid}/reject", headers=ceo_headers)

        response = client.get("/api/v1/approvals/stats", headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["pending"] == 2
        assert data["approved"] == 1
        assert data["rejected"] == 1
        assert data["total"] == 4

    def test_stats_after_cancel(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "low",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        aid = create_resp.json()["id"]
        client.post(f"/api/v1/approvals/{aid}/cancel", headers=ceo_headers)

        response = client.get("/api/v1/approvals/stats", headers=ceo_headers)
        data = response.json()
        assert data["cancelled"] == 1
        assert data["pending"] == 0

    def test_stats_requires_auth(self, client):
        response = client.get("/api/v1/approvals/stats")
        assert response.status_code == 401


class TestApprovalEvents:
    def test_events_recorded_on_create(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        response = client.get(
            f"/api/v1/approvals/{approval_id}/events",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 1
        assert events[0]["event_type"] == "created"
        assert events[0]["old_status"] is None
        assert events[0]["new_status"] == "pending"

    def test_events_recorded_on_approve(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "medium",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            params={"notes": "Approved"},
            headers=ceo_headers,
        )

        response = client.get(
            f"/api/v1/approvals/{approval_id}/events",
            headers=ceo_headers,
        )
        events = response.json()
        assert len(events) == 2
        event_types = [e["event_type"] for e in events]
        assert "created" in event_types
        assert "approved" in event_types

    def test_events_recorded_on_reject(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "delete_database",
            "risk_level": "critical",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            params={"notes": "Denied"},
            headers=ceo_headers,
        )

        response = client.get(
            f"/api/v1/approvals/{approval_id}/events",
            headers=ceo_headers,
        )
        events = response.json()
        assert len(events) == 2
        reject_event = [e for e in events if e["event_type"] == "rejected"][0]
        assert reject_event["old_status"] == "pending"
        assert reject_event["new_status"] == "rejected"

    def test_events_recorded_on_cancel(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "low",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        client.post(f"/api/v1/approvals/{approval_id}/cancel", headers=ceo_headers)

        response = client.get(
            f"/api/v1/approvals/{approval_id}/events",
            headers=ceo_headers,
        )
        events = response.json()
        assert len(events) == 2
        cancel_event = [e for e in events if e["event_type"] == "cancelled"][0]
        assert cancel_event["new_status"] == "cancelled"

    def test_events_empty_for_no_activity(self, client, ceo_headers, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "low",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload, headers=ceo_headers)
        approval_id = create_resp.json()["id"]

        response = client.get(
            f"/api/v1/approvals/{approval_id}/events",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        events = response.json()
        assert len(events) == 1
        assert events[0]["event_type"] == "created"

    def test_events_requires_auth(self, client, sample_agent):
        payload = {
            "agent_id": str(sample_agent.id),
            "action": "send_email",
            "risk_level": "low",
        }
        create_resp = client.post("/api/v1/approvals/", json=payload)
        assert create_resp.status_code == 401
