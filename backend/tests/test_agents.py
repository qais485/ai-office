import pytest
from uuid import uuid4

from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.room import OfficeRoom, RoomStatus, RoomVisualStatus
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services.agent_service import AgentService
from app.services.hiring_service import HiringService


# ---------------------------------------------------------------------------
# TestAgentCRUD - Create, read, update, delete agents via API
# ---------------------------------------------------------------------------

class TestAgentCRUD:
    def test_create_agent(self, client, ceo_headers):
        resp = client.post(
            "/api/v1/agents/",
            json={"name": "New Agent", "role": "assistant", "description": "A new agent"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Agent"
        assert data["role"] == "assistant"
        assert data["description"] == "A new agent"
        assert "id" in data

    def test_create_agent_minimal_fields(self, client, ceo_headers):
        resp = client.post(
            "/api/v1/agents/",
            json={"name": "Minimal Agent", "role": "analyst"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Minimal Agent"
        assert data["role"] == "analyst"
        assert data["description"] is None

    def test_list_agents(self, client, ceo_headers, sample_agent):
        resp = client.get("/api/v1/agents/", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        names = [a["name"] for a in data]
        assert "Test Agent" in names

    def test_get_agent_by_id(self, client, ceo_headers, sample_agent):
        resp = client.get(f"/api/v1/agents/{sample_agent.id}", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Agent"
        assert data["id"] == str(sample_agent.id)

    def test_get_nonexistent_agent_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.get(f"/api/v1/agents/{fake_id}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_update_agent(self, client, ceo_headers, sample_agent):
        resp = client.put(
            f"/api/v1/agents/{sample_agent.id}",
            json={"name": "Updated Agent", "description": "Updated description"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Agent"
        assert data["description"] == "Updated description"

    def test_update_agent_status(self, client, ceo_headers, sample_agent):
        resp = client.put(
            f"/api/v1/agents/{sample_agent.id}",
            json={"status": "active"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_update_nonexistent_agent_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.put(
            f"/api/v1/agents/{fake_id}",
            json={"name": "No Agent"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_delete_agent(self, client, ceo_headers, sample_agent):
        resp = client.delete(f"/api/v1/agents/{sample_agent.id}", headers=ceo_headers)
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Agent deleted"

        get_resp = client.get(f"/api/v1/agents/{sample_agent.id}", headers=ceo_headers)
        assert get_resp.status_code == 404

    def test_delete_nonexistent_agent_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.delete(f"/api/v1/agents/{fake_id}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_create_agent_requires_auth(self, client):
        resp = client.post(
            "/api/v1/agents/",
            json={"name": "Unauth Agent", "role": "assistant"},
        )
        assert resp.status_code == 401

    def test_regular_user_can_create_agent(self, client, user_headers):
        resp = client.post(
            "/api/v1/agents/",
            json={"name": "User Agent", "role": "writer"},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "User Agent"


# ---------------------------------------------------------------------------
# TestAgentStatusTransitions - Valid and invalid lifecycle transitions
# ---------------------------------------------------------------------------

class TestAgentStatusTransitions:
    def test_draft_to_active(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.DRAFT
        db.commit()
        db.refresh(neon_agent)

        result = service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.ACTIVE)
        assert result is not None
        assert result.lifecycle_status == LifecycleStatus.ACTIVE
        assert result.status == "active"

    def test_active_to_paused(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ACTIVE
        neon_agent.status = "active"
        db.commit()
        db.refresh(neon_agent)

        result = service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.PAUSED)
        assert result.lifecycle_status == LifecycleStatus.PAUSED
        assert result.status == "inactive"
        assert result.paused_at is not None

    def test_active_to_disabled(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ACTIVE
        neon_agent.status = "active"
        db.commit()
        db.refresh(neon_agent)

        result = service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.DISABLED)
        assert result.lifecycle_status == LifecycleStatus.DISABLED
        assert result.status == "inactive"
        assert result.disabled_at is not None

    def test_active_to_error(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ACTIVE
        neon_agent.status = "active"
        db.commit()
        db.refresh(neon_agent)

        result = service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.ERROR)
        assert result.lifecycle_status == LifecycleStatus.ERROR
        assert result.status == "inactive"

    def test_paused_to_active(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.PAUSED
        neon_agent.status = "inactive"
        db.commit()
        db.refresh(neon_agent)

        result = service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.ACTIVE)
        assert result.lifecycle_status == LifecycleStatus.ACTIVE
        assert result.status == "active"
        assert result.last_active_at is not None

    def test_paused_to_disabled(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.PAUSED
        neon_agent.status = "inactive"
        db.commit()
        db.refresh(neon_agent)

        result = service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.DISABLED)
        assert result.lifecycle_status == LifecycleStatus.DISABLED

    def test_error_to_active(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ERROR
        neon_agent.status = "inactive"
        db.commit()
        db.refresh(neon_agent)

        result = service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.ACTIVE)
        assert result.lifecycle_status == LifecycleStatus.ACTIVE
        assert result.status == "active"
        assert result.last_error is None

    def test_error_to_disabled(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ERROR
        neon_agent.status = "inactive"
        db.commit()
        db.refresh(neon_agent)

        result = service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.DISABLED)
        assert result.lifecycle_status == LifecycleStatus.DISABLED

    def test_disabled_to_active(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.DISABLED
        neon_agent.status = "inactive"
        db.commit()
        db.refresh(neon_agent)

        result = service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.ACTIVE)
        assert result.lifecycle_status == LifecycleStatus.ACTIVE
        assert result.status == "active"

    def test_invalid_transition_draft_to_paused(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.DRAFT
        db.commit()
        db.refresh(neon_agent)

        with pytest.raises(ValueError, match="Cannot transition"):
            service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.PAUSED)

    def test_invalid_transition_active_to_draft(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ACTIVE
        neon_agent.status = "active"
        db.commit()
        db.refresh(neon_agent)

        with pytest.raises(ValueError, match="Cannot transition"):
            service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.DRAFT)

    def test_invalid_transition_paused_to_error(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.PAUSED
        neon_agent.status = "inactive"
        db.commit()
        db.refresh(neon_agent)

        with pytest.raises(ValueError, match="Cannot transition"):
            service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.ERROR)

    def test_invalid_transition_disabled_to_paused(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.DISABLED
        neon_agent.status = "inactive"
        db.commit()
        db.refresh(neon_agent)

        with pytest.raises(ValueError, match="Cannot transition"):
            service.update_agent_lifecycle(neon_agent.id, LifecycleStatus.PAUSED)

    def test_transition_nonexistent_agent_returns_none(self, db):
        service = HiringService(db)
        result = service.update_agent_lifecycle(uuid4(), LifecycleStatus.ACTIVE)
        assert result is None


# ---------------------------------------------------------------------------
# TestAgentLifecycle - Pause, resume, disable, archive, error, restart
# ---------------------------------------------------------------------------

class TestAgentLifecycle:
    def test_pause_agent(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ACTIVE
        neon_agent.status = "active"
        db.commit()
        db.refresh(neon_agent)

        result = service.pause_agent(neon_agent.id)
        assert result is not None
        assert result.lifecycle_status == LifecycleStatus.PAUSED
        assert result.paused_at is not None

    def test_resume_agent(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.PAUSED
        neon_agent.status = "inactive"
        db.commit()
        db.refresh(neon_agent)

        result = service.resume_agent(neon_agent.id)
        assert result is not None
        assert result.lifecycle_status == LifecycleStatus.ACTIVE
        assert result.status == "active"

    def test_disable_agent(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ACTIVE
        neon_agent.status = "active"
        db.commit()
        db.refresh(neon_agent)

        result = service.disable_agent(neon_agent.id, reason="Performance issues")
        assert result is not None
        assert result.lifecycle_status == LifecycleStatus.DISABLED
        assert result.disabled_reason == "Performance issues"
        assert result.disabled_at is not None

    def test_disable_agent_without_reason(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ACTIVE
        neon_agent.status = "active"
        db.commit()
        db.refresh(neon_agent)

        result = service.disable_agent(neon_agent.id)
        assert result is not None
        assert result.lifecycle_status == LifecycleStatus.DISABLED
        assert result.disabled_reason is None

    def test_archive_agent(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.DISABLED
        neon_agent.status = "inactive"
        db.commit()
        db.refresh(neon_agent)

        result = service.archive_agent(neon_agent.id)
        assert result is not None
        assert result.lifecycle_status == LifecycleStatus.ARCHIVED
        assert result.archived_at is not None

    def test_set_error(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ACTIVE
        neon_agent.status = "active"
        db.commit()
        db.refresh(neon_agent)

        result = service.set_error(neon_agent.id, "Connection timeout")
        assert result is not None
        assert result.lifecycle_status == LifecycleStatus.ERROR
        assert result.last_error == "Connection timeout"
        assert result.status == "inactive"

    def test_restart_agent_from_error(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ERROR
        neon_agent.status = "inactive"
        neon_agent.last_error = "Some error"
        db.commit()
        db.refresh(neon_agent)

        result = service.restart_agent(neon_agent.id)
        assert result is not None
        assert result.lifecycle_status == LifecycleStatus.ACTIVE
        assert result.status == "active"
        assert result.last_error is None

    def test_restart_agent_not_in_error_raises(self, db, neon_agent):
        service = HiringService(db)
        neon_agent.lifecycle_status = LifecycleStatus.ACTIVE
        neon_agent.status = "active"
        db.commit()
        db.refresh(neon_agent)

        with pytest.raises(ValueError, match="Can only restart agents in error state"):
            service.restart_agent(neon_agent.id)

    def test_pause_nonexistent_agent_returns_none(self, db):
        service = HiringService(db)
        result = service.pause_agent(uuid4())
        assert result is None

    def test_resume_nonexistent_agent_returns_none(self, db):
        service = HiringService(db)
        result = service.resume_agent(uuid4())
        assert result is None

    def test_disable_nonexistent_agent_returns_none(self, db):
        service = HiringService(db)
        result = service.disable_agent(uuid4())
        assert result is None

    def test_archive_nonexistent_agent_returns_none(self, db):
        service = HiringService(db)
        result = service.archive_agent(uuid4())
        assert result is None

    def test_set_error_nonexistent_agent_returns_none(self, db):
        service = HiringService(db)
        result = service.set_error(uuid4(), "error")
        assert result is None

    def test_restart_nonexistent_agent_returns_none(self, db):
        service = HiringService(db)
        result = service.restart_agent(uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# TestAgentRoomAssignment - Agent can be assigned to a room
# ---------------------------------------------------------------------------

class TestAgentRoomAssignment:
    def test_create_agent_with_room(self, client, ceo_headers, sample_room):
        resp = client.post(
            "/api/v1/agents/",
            json={
                "name": "Room Agent",
                "role": "assistant",
                "room_id": str(sample_room.id),
            },
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["room_id"] == str(sample_room.id)

    def test_update_agent_room(self, client, ceo_headers, sample_agent, sample_room):
        resp = client.put(
            f"/api/v1/agents/{sample_agent.id}",
            json={"room_id": str(sample_room.id)},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["room_id"] == str(sample_room.id)

    def test_remove_agent_from_room(self, client, ceo_headers, sample_agent):
        resp = client.put(
            f"/api/v1/agents/{sample_agent.id}",
            json={"room_id": None},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["room_id"] is None

    def test_agent_reflects_room_in_list(self, client, ceo_headers, sample_agent, sample_room):
        resp = client.get("/api/v1/agents/", headers=ceo_headers)
        assert resp.status_code == 200
        agents = resp.json()
        agent = next(a for a in agents if a["id"] == str(sample_agent.id))
        assert agent["room_id"] == str(sample_room.id)

    def test_agent_reflects_room_in_detail(self, client, ceo_headers, sample_agent, sample_room):
        resp = client.get(f"/api/v1/agents/{sample_agent.id}", headers=ceo_headers)
        assert resp.status_code == 200
        assert resp.json()["room_id"] == str(sample_room.id)

    def test_assign_agent_to_new_room(self, client, ceo_headers, sample_agent, api_db):
        new_room = OfficeRoom(
            id=uuid4(),
            name="Second Room",
            description="Another room",
            status=RoomStatus.AVAILABLE,
            visual_status=RoomVisualStatus.OFFLINE,
            room_type="meeting",
            capacity="4",
        )
        api_db.add(new_room)
        api_db.flush()

        resp = client.put(
            f"/api/v1/agents/{sample_agent.id}",
            json={"room_id": str(new_room.id)},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["room_id"] == str(new_room.id)
