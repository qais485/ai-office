import pytest
from uuid import uuid4

from app.models.user import User
from app.utils.security import create_access_token


# ---------------------------------------------------------------------------
# Roles were removed: the /users management endpoints no longer exist and
# every account is a plain user scoped to its own data. What remains here
# covers /auth/me and inactive-account handling.
# ---------------------------------------------------------------------------

class TestUserInfo:
    def test_can_get_own_info(self, client, ceo_headers, ceo_user):
        resp = client.get("/api/v1/auth/me", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "ceo@test.com"
        assert data["name"] == "Test CEO"
        assert data["role"] == "user"
        assert data["is_active"] is True

    def test_regular_user_can_get_own_info(self, client, user_headers, regular_user):
        resp = client.get("/api/v1/auth/me", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@test.com"
        assert data["name"] == "Test User"
        assert data["role"] == "user"

    def test_me_returns_correct_id(self, client, ceo_headers, ceo_user):
        resp = client.get("/api/v1/auth/me", headers=ceo_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == str(ceo_user.id)

    def test_unauthenticated_user_cannot_get_me(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_invalid_token_cannot_get_me(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.value"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# TestUserDeactivation - Inactive users cannot access protected endpoints
# ---------------------------------------------------------------------------

class TestUserDeactivation:
    def _make_inactive_user(self, api_db):
        user = User(
            id=uuid4(),
            email="inactive@test.com",
            name="Inactive User",
            role="user",
            is_active=False,
        )
        api_db.add(user)
        api_db.flush()
        token = create_access_token(data={"sub": str(user.id)})
        return user, {"Authorization": f"Bearer {token}"}

    def test_inactive_user_cannot_access_me(self, client, api_db):
        user, headers = self._make_inactive_user(api_db)
        resp = client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 403

    def test_inactive_user_cannot_list_agents(self, client, api_db):
        user, headers = self._make_inactive_user(api_db)
        resp = client.get("/api/v1/agents/", headers=headers)
        assert resp.status_code == 403

    def test_inactive_user_cannot_create_agent(self, client, api_db):
        user, headers = self._make_inactive_user(api_db)
        resp = client.post(
            "/api/v1/agents/",
            json={"name": "Agent", "role": "assistant"},
            headers=headers,
        )
        assert resp.status_code == 403
