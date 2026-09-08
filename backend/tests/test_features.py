import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.session import Base, get_db
from app.models.user import User
from app.utils.security import create_access_token

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_features.db"
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


@pytest.fixture
def ceo_user(db_session):
    user = User(
        id=uuid4(),
        email="ceo@test.com",
        name="Test CEO",
        role="user",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(ceo_user):
    token = create_access_token(data={"sub": str(ceo_user.id)})
    return {"Authorization": f"Bearer {token}"}


class TestTemplates:
    def test_get_templates(self, client, auth_headers):
        response = client.get("/api/v1/templates/", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_template_by_id(self, client, auth_headers):
        response = client.get("/api/v1/templates/", headers=auth_headers)
        if response.json():
            template_id = response.json()[0]["id"]
            response = client.get(f"/api/v1/templates/{template_id}", headers=auth_headers)
            assert response.status_code == 200


class TestHiring:
    def test_get_templates_for_hiring(self, client, auth_headers):
        response = client.get("/api/v1/hiring/templates", headers=auth_headers)
        assert response.status_code == 200


class TestPermissions:
    def test_get_permissions(self, client, auth_headers):
        response = client.get("/api/v1/permissions/", headers=auth_headers)
        assert response.status_code == 200


class TestApprovals:
    def test_get_approvals(self, client, auth_headers):
        response = client.get("/api/v1/approvals/", headers=auth_headers)
        assert response.status_code == 200
    
    def test_get_pending_approvals(self, client, auth_headers):
        response = client.get("/api/v1/approvals/?status=pending", headers=auth_headers)
        assert response.status_code == 200


class TestTools:
    def test_get_tools(self, client, auth_headers):
        response = client.get("/api/v1/tools/", headers=auth_headers)
        assert response.status_code == 200


class TestKnowledge:
    def test_get_knowledge(self, client, auth_headers):
        response = client.get("/api/v1/knowledge/", headers=auth_headers)
        assert response.status_code == 200
    
    def test_get_knowledge_stats(self, client, auth_headers):
        response = client.get("/api/v1/knowledge/stats", headers=auth_headers)
        assert response.status_code == 200
    
    def test_search_knowledge(self, client, auth_headers):
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "test", "limit": 5},
            headers=auth_headers
        )
        assert response.status_code == 200


class TestAnalytics:
    def test_get_company_analytics(self, client, auth_headers):
        response = client.get("/api/v1/analytics/company", headers=auth_headers)
        assert response.status_code == 200
    
    def test_get_agent_ranking(self, client, auth_headers):
        response = client.get("/api/v1/analytics/ranking", headers=auth_headers)
        assert response.status_code == 200
    
    def test_get_daily_stats(self, client, auth_headers):
        response = client.get("/api/v1/analytics/daily", headers=auth_headers)
        assert response.status_code == 200


class TestCollaboration:
    def test_get_collaboration_stats(self, client, auth_headers):
        response = client.get("/api/v1/collaboration/stats", headers=auth_headers)
        assert response.status_code == 200


class TestCEODashboard:
    def test_get_dashboard_summary(self, client, auth_headers):
        response = client.get("/api/v1/ceo/dashboard/summary", headers=auth_headers)
        assert response.status_code == 200
    
    def test_get_inbox(self, client, auth_headers):
        response = client.get("/api/v1/ceo/inbox/", headers=auth_headers)
        assert response.status_code == 200
