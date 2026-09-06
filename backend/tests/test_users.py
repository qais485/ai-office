import pytest
from uuid import uuid4

from app.models.user import User, UserRole
from app.utils.security import create_access_token


# ---------------------------------------------------------------------------
# TestUserList - CEO can list, admin cannot, regular user cannot
# ---------------------------------------------------------------------------

class TestUserList:
    def test_ceo_can_list_users(self, client, ceo_headers):
        resp = client.get("/api/v1/users/", headers=ceo_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_ceo_list_includes_created_users(self, client, ceo_headers, ceo_user, admin_user, regular_user):
        resp = client.get("/api/v1/users/", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        emails = [u["email"] for u in data]
        assert "ceo@test.com" in emails
        assert "admin@test.com" in emails
        assert "user@test.com" in emails

    def test_admin_cannot_list_users(self, client, admin_headers):
        resp = client.get("/api/v1/users/", headers=admin_headers)
        assert resp.status_code == 403

    def test_regular_user_cannot_list_users(self, client, user_headers):
        resp = client.get("/api/v1/users/", headers=user_headers)
        assert resp.status_code == 403

    def test_unauthenticated_user_cannot_list_users(self, client):
        resp = client.get("/api/v1/users/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# TestUserRoleUpdate - CEO can update, admin/user cannot, invalid rejected
# ---------------------------------------------------------------------------

class TestUserRoleUpdate:
    def test_ceo_can_update_user_role(self, client, ceo_headers, regular_user):
        resp = client.put(
            f"/api/v1/users/{regular_user.id}/role",
            json={"role": "admin"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_ceo_can_demote_admin_to_user(self, client, ceo_headers, admin_user):
        resp = client.put(
            f"/api/v1/users/{admin_user.id}/role",
            json={"role": "user"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"

    def test_ceo_can_set_ceo_role(self, client, ceo_headers, regular_user):
        resp = client.put(
            f"/api/v1/users/{regular_user.id}/role",
            json={"role": "ceo"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "ceo"

    def test_admin_cannot_update_user_role(self, client, admin_headers, regular_user):
        resp = client.put(
            f"/api/v1/users/{regular_user.id}/role",
            json={"role": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 403

    def test_regular_user_cannot_update_user_role(self, client, user_headers, admin_user):
        resp = client.put(
            f"/api/v1/users/{admin_user.id}/role",
            json={"role": "user"},
            headers=user_headers,
        )
        assert resp.status_code == 403

    def test_invalid_role_rejected(self, client, ceo_headers, regular_user):
        resp = client.put(
            f"/api/v1/users/{regular_user.id}/role",
            json={"role": "superadmin"},
            headers=ceo_headers,
        )
        assert resp.status_code == 422

    def test_update_nonexistent_user_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.put(
            f"/api/v1/users/{fake_id}/role",
            json={"role": "admin"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_role_update_reflected_in_get(self, client, ceo_headers, regular_user):
        client.put(
            f"/api/v1/users/{regular_user.id}/role",
            json={"role": "admin"},
            headers=ceo_headers,
        )
        resp = client.get(f"/api/v1/users/{regular_user.id}", headers=ceo_headers)
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"


# ---------------------------------------------------------------------------
# TestUserInfo - Any user can get their own info via /api/v1/auth/me
# ---------------------------------------------------------------------------

class TestUserInfo:
    def test_ceo_can_get_own_info(self, client, ceo_headers, ceo_user):
        resp = client.get("/api/v1/auth/me", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "ceo@test.com"
        assert data["name"] == "Test CEO"
        assert data["role"] == "ceo"
        assert data["is_active"] is True

    def test_admin_can_get_own_info(self, client, admin_headers, admin_user):
        resp = client.get("/api/v1/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@test.com"
        assert data["name"] == "Test Admin"
        assert data["role"] == "admin"

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
            role=UserRole.USER,
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

    def test_inactive_user_cannot_list_users(self, client, api_db):
        user, headers = self._make_inactive_user(api_db)
        resp = client.get("/api/v1/users/", headers=headers)
        assert resp.status_code == 403

    def test_inactive_user_cannot_update_role(self, client, api_db, ceo_user):
        user, headers = self._make_inactive_user(api_db)
        resp = client.put(
            f"/api/v1/users/{ceo_user.id}/role",
            json={"role": "admin"},
            headers=headers,
        )
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
