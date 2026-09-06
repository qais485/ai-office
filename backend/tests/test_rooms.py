import pytest
from uuid import uuid4

from app.models.room import OfficeRoom, RoomStatus, RoomVisualStatus


# ---------------------------------------------------------------------------
# TestRoomCRUD
# ---------------------------------------------------------------------------

class TestRoomCRUD:
    def test_create_room(self, client, ceo_headers):
        resp = client.post(
            "/api/v1/rooms/",
            json={
                "name": "New Room",
                "description": "Brand new room",
                "room_type": "meeting",
            },
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Room"
        assert data["description"] == "Brand new room"
        assert data["room_type"] == "meeting"
        assert data["status"] == "available"
        assert data["visual_status"] == "offline"
        assert "id" in data

    def test_create_room_minimal_fields(self, client, ceo_headers):
        resp = client.post(
            "/api/v1/rooms/",
            json={"name": "Minimal Room"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Minimal Room"
        assert data["description"] is None
        assert data["room_type"] is None
        assert data["status"] == "available"

    def test_list_rooms(self, client, ceo_headers, sample_room):
        resp = client.get("/api/v1/rooms/", headers=ceo_headers)
        assert resp.status_code == 200
        rooms = resp.json()
        assert isinstance(rooms, list)
        assert len(rooms) >= 1
        ids = [r["id"] for r in rooms]
        assert str(sample_room.id) in ids

    def test_get_room_by_id(self, client, ceo_headers, sample_room):
        resp = client.get(f"/api/v1/rooms/{sample_room.id}", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(sample_room.id)
        assert data["name"] == "Test Room"

    def test_get_room_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.get(f"/api/v1/rooms/{fake_id}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_update_room(self, client, ceo_headers, sample_room):
        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={
                "name": "Updated Room",
                "description": "Updated description",
                "status": "maintenance",
            },
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Room"
        assert data["description"] == "Updated description"
        assert data["status"] == "maintenance"

    def test_update_room_partial(self, client, ceo_headers, sample_room):
        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"name": "Partially Updated"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Partially Updated"
        assert data["description"] == "A test office room"

    def test_update_room_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.put(
            f"/api/v1/rooms/{fake_id}",
            json={"name": "Ghost Room"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_delete_room(self, client, ceo_headers, sample_room):
        resp = client.delete(f"/api/v1/rooms/{sample_room.id}", headers=ceo_headers)
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Room deleted"
        get_resp = client.get(f"/api/v1/rooms/{sample_room.id}", headers=ceo_headers)
        assert get_resp.status_code == 404

    def test_delete_room_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.delete(f"/api/v1/rooms/{fake_id}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_create_multiple_rooms(self, client, ceo_headers):
        for i in range(3):
            resp = client.post(
                "/api/v1/rooms/",
                json={"name": f"Room {i}"},
                headers=ceo_headers,
            )
            assert resp.status_code == 200

        list_resp = client.get("/api/v1/rooms/", headers=ceo_headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 3

    def test_unauthenticated_cannot_create_room(self, client):
        resp = client.post(
            "/api/v1/rooms/",
            json={"name": "Unauthorized Room"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# TestRoomStatus
# ---------------------------------------------------------------------------

class TestRoomStatus:
    def test_default_room_status_is_available(self, client, ceo_headers):
        resp = client.post(
            "/api/v1/rooms/",
            json={"name": "Status Room"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "available"

    def test_update_status_to_occupied(self, client, ceo_headers, sample_room):
        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"status": "occupied"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "occupied"

    def test_update_status_to_maintenance(self, client, ceo_headers, sample_room):
        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"status": "maintenance"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "maintenance"

    def test_status_transition_available_to_occupied_to_available(
        self, client, ceo_headers, sample_room
    ):
        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"status": "occupied"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "occupied"

        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"status": "available"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "available"

    def test_update_visual_status(self, client, ceo_headers, sample_room):
        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"visual_status": "online_active"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["visual_status"] == "online_active"

    def test_update_visual_status_needs_attention(self, client, ceo_headers, sample_room):
        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"visual_status": "needs_attention"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["visual_status"] == "needs_attention"

    def test_update_visual_status_error(self, client, ceo_headers, sample_room):
        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"visual_status": "error"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["visual_status"] == "error"

    def test_update_room_config(self, client, ceo_headers, sample_room):
        config = {"theme": "dark", "notifications": True}
        resp = client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"room_config": config},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["room_config"] == config


# ---------------------------------------------------------------------------
# TestRoomEnterLeave
# ---------------------------------------------------------------------------

class TestRoomEnterLeave:
    def test_enter_room(self, client, ceo_headers, sample_room):
        resp = client.post(
            f"/api/v1/rooms/{sample_room.id}/enter",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["room"]["id"] == str(sample_room.id)

    def test_enter_room_sets_status_to_occupied(self, client, ceo_headers, sample_room):
        client.post(
            f"/api/v1/rooms/{sample_room.id}/enter",
            headers=ceo_headers,
        )
        room_resp = client.get(
            f"/api/v1/rooms/{sample_room.id}", headers=ceo_headers
        )
        assert room_resp.status_code == 200
        assert room_resp.json()["status"] == "occupied"

    def test_enter_room_sets_current_user_id(self, client, ceo_headers, ceo_user):
        client.post(
            f"/api/v1/rooms/{sample_room.id}/enter",
            headers=ceo_headers,
        )
        room_resp = client.get(
            f"/api/v1/rooms/{sample_room.id}", headers=ceo_headers
        )
        assert room_resp.status_code == 200
        assert room_resp.json()["current_user_id"] == str(ceo_user.id)

    def test_leave_room(self, client, ceo_headers, sample_room):
        client.post(
            f"/api/v1/rooms/{sample_room.id}/enter",
            headers=ceo_headers,
        )
        resp = client.post(
            f"/api/v1/rooms/{sample_room.id}/leave",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_leave_room_sets_status_to_available(
        self, client, ceo_headers, sample_room
    ):
        client.post(
            f"/api/v1/rooms/{sample_room.id}/enter",
            headers=ceo_headers,
        )
        client.post(
            f"/api/v1/rooms/{sample_room.id}/leave",
            headers=ceo_headers,
        )
        room_resp = client.get(
            f"/api/v1/rooms/{sample_room.id}", headers=ceo_headers
        )
        assert room_resp.status_code == 200
        assert room_resp.json()["status"] == "available"

    def test_leave_room_clears_current_user_id(
        self, client, ceo_headers, sample_room
    ):
        client.post(
            f"/api/v1/rooms/{sample_room.id}/enter",
            headers=ceo_headers,
        )
        client.post(
            f"/api/v1/rooms/{sample_room.id}/leave",
            headers=ceo_headers,
        )
        room_resp = client.get(
            f"/api/v1/rooms/{sample_room.id}", headers=ceo_headers
        )
        assert room_resp.status_code == 200
        assert room_resp.json()["current_user_id"] is None

    def test_enter_room_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.post(
            f"/api/v1/rooms/{fake_id}/enter",
            headers=ceo_headers,
        )
        assert resp.status_code == 400

    def test_leave_room_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.post(
            f"/api/v1/rooms/{fake_id}/leave",
            headers=ceo_headers,
        )
        assert resp.status_code == 400

    def test_leave_room_not_entered(self, client, ceo_headers, sample_room):
        resp = client.post(
            f"/api/v1/rooms/{sample_room.id}/leave",
            headers=ceo_headers,
        )
        assert resp.status_code == 400

    def test_enter_leave_enter_cycle(self, client, ceo_headers, sample_room):
        resp1 = client.post(
            f"/api/v1/rooms/{sample_room.id}/enter",
            headers=ceo_headers,
        )
        assert resp1.status_code == 200
        assert resp1.json()["success"] is True

        resp2 = client.post(
            f"/api/v1/rooms/{sample_room.id}/leave",
            headers=ceo_headers,
        )
        assert resp2.status_code == 200

        resp3 = client.post(
            f"/api/v1/rooms/{sample_room.id}/enter",
            headers=ceo_headers,
        )
        assert resp3.status_code == 200
        assert resp3.json()["success"] is True

        room_resp = client.get(
            f"/api/v1/rooms/{sample_room.id}", headers=ceo_headers
        )
        assert room_resp.json()["status"] == "occupied"


# ---------------------------------------------------------------------------
# TestRoomStatuses
# ---------------------------------------------------------------------------

class TestRoomStatuses:
    def test_get_room_statuses(self, client, ceo_headers, sample_room):
        resp = client.get("/api/v1/rooms/statuses", headers=ceo_headers)
        assert resp.status_code == 200
        statuses = resp.json()
        assert isinstance(statuses, list)
        assert len(statuses) >= 1

    def test_room_statuses_contain_expected_fields(
        self, client, ceo_headers, sample_room
    ):
        resp = client.get("/api/v1/rooms/statuses", headers=ceo_headers)
        assert resp.status_code == 200
        statuses = resp.json()
        room_status = next(
            (s for s in statuses if s["room_id"] == str(sample_room.id)), None
        )
        assert room_status is not None
        assert "room_id" in room_status
        assert "name" in room_status
        assert "visual_status" in room_status
        assert "has_pending_approvals" in room_status
        assert "task_count" in room_status

    def test_room_statuses_empty_when_no_rooms(self, client, ceo_headers):
        resp = client.get("/api/v1/rooms/statuses", headers=ceo_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_room_statuses_reflect_visual_status(
        self, client, ceo_headers, sample_room
    ):
        client.put(
            f"/api/v1/rooms/{sample_room.id}",
            json={"visual_status": "online_active"},
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/rooms/statuses", headers=ceo_headers)
        assert resp.status_code == 200
        room_status = next(
            (s for s in resp.json() if s["room_id"] == str(sample_room.id)), None
        )
        assert room_status is not None
        assert room_status["visual_status"] == "online_active"

    def test_room_statuses_multiple_rooms(self, client, ceo_headers):
        ids = []
        for i in range(3):
            resp = client.post(
                "/api/v1/rooms/",
                json={"name": f"Status Room {i}"},
                headers=ceo_headers,
            )
            assert resp.status_code == 200
            ids.append(resp.json()["id"])

        resp = client.get("/api/v1/rooms/statuses", headers=ceo_headers)
        assert resp.status_code == 200
        statuses = resp.json()
        returned_ids = [s["room_id"] for s in statuses]
        for rid in ids:
            assert rid in returned_ids
