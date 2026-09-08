import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.session import Base, get_db
from app.utils.security import create_access_token

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def _mock_google_token(sub: str = "google-123", email: str = "user@gmail.com", name: str = "Test User", picture: str = None):
    return {
        "sub": sub,
        "email": email,
        "name": name,
        "picture": picture,
    }


def _google_login(client: TestClient, sub: str = "google-123", email: str = "user@gmail.com", name: str = "Test User"):
    mock_info = _mock_google_token(sub=sub, email=email, name=name)
    with patch("app.api.v1.endpoints.auth.id_token.verify_oauth2_token", return_value=mock_info):
        return client.post("/api/v1/auth/google", json={"credential": "fake-google-token"})


# ---------------------------------------------------------------------------
# Google OAuth tests
# ---------------------------------------------------------------------------

class TestGoogleLogin:
    def test_google_login_creates_new_user(self, client):
        resp = _google_login(client)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_google_login_returns_user_data(self, client):
        _google_login(client)
        resp = _google_login(client)
        token = resp.json()["access_token"]
        me_resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["email"] == "user@gmail.com"
        assert data["name"] == "Test User"
        assert data["is_active"] is True

    def test_google_login_existing_user(self, client):
        _google_login(client, sub="g-1", email="a@gmail.com", name="A")
        resp = _google_login(client, sub="g-1", email="a@gmail.com", name="A Updated")
        token = resp.json()["access_token"]
        me_resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
        assert me_resp.json()["name"] == "A Updated"

    def test_google_login_invalid_token(self, client):
        with patch("app.api.v1.endpoints.auth.id_token.verify_oauth2_token", side_effect=Exception("invalid")):
            resp = client.post("/api/v1/auth/google", json={"credential": "bad-token"})
        assert resp.status_code == 401

    def test_every_user_gets_plain_user_role(self, client):
        # Roles were removed: there is no first-user "ceo" promotion anymore.
        _google_login(client, sub="first", email="first@gmail.com", name="First")
        resp = _google_login(client, sub="first", email="first@gmail.com", name="First")
        token = resp.json()["access_token"]
        me_resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
        assert me_resp.json()["role"] == "user"

    def test_second_user_gets_user_role(self, client):
        _google_login(client, sub="first", email="first@gmail.com", name="First")
        _google_login(client, sub="second", email="second@gmail.com", name="Second")
        resp = _google_login(client, sub="second", email="second@gmail.com", name="Second")
        token = resp.json()["access_token"]
        me_resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
        assert me_resp.json()["role"] == "user"


# ---------------------------------------------------------------------------
# Profile tests
# ---------------------------------------------------------------------------

class TestProfile:
    def _get_token(self, client) -> str:
        resp = _google_login(client)
        return resp.json()["access_token"]

    def test_get_me(self, client):
        token = self._get_token(client)
        resp = client.get("/api/v1/auth/me", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@gmail.com"

    def test_get_me_no_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        resp = client.get("/api/v1/auth/me", headers=_auth_header("bad.token.here"))
        assert resp.status_code == 401

    def test_update_me(self, client):
        token = self._get_token(client)
        resp = client.put(
            "/api/v1/auth/me",
            json={"name": "Updated"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"


# ---------------------------------------------------------------------------
# Users management endpoints were removed along with roles.
# ---------------------------------------------------------------------------

class TestRoleAccess:
    def _create_user_via_google(self, client, sub: str, email: str) -> str:
        resp = _google_login(client, sub=sub, email=email, name=email.split("@")[0])
        return resp.json()["access_token"]

    def test_users_list_endpoint_removed(self, client, db_session):
        token = self._create_user_via_google(client, "g-1", "regular@test.com")
        resp = client.get("/api/v1/users/", headers=_auth_header(token))
        assert resp.status_code in (404, 405)

    def test_role_update_endpoint_removed(self, client, db_session):
        token_user = self._create_user_via_google(client, "g-2", "promote@test.com")
        me_resp = client.get("/api/v1/auth/me", headers=_auth_header(token_user))
        user_id = me_resp.json()["id"]
        resp = client.put(
            f"/api/v1/users/{user_id}/role",
            json={"role": "admin"},
            headers=_auth_header(token_user),
        )
        assert resp.status_code in (404, 405)
