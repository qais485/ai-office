"""Shared test fixtures for the comprehensive test suite.

Uses SQLite for API tests and Neon DB for service tests.
"""
import asyncio
import os
import sys
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

# Ensure the backend directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.core.config import settings
from app.models.user import User
from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.room import OfficeRoom, RoomStatus, RoomVisualStatus
from app.models.task import Task, TaskStatus, TaskPriority, TaskType
from app.models.approval import Approval
from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.models.permission import Permission
from app.models.agent_permission import AgentPermission
from app.models.integration import Integration
from app.models.integration_account import IntegrationAccount
from app.models.agent_integration import AgentIntegration
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.risk_rule import RiskRule
from app.models.knowledge import KnowledgeSource, KnowledgeStatus
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.template import AgentTemplate
from app.models.email_account import EmailAccount
from app.models.email import EmailMessage, EmailStatus
from app.utils.security import create_access_token
from app.utils.encryption import encrypt_field


# ---------------------------------------------------------------------------
# SQLite engine for API tests
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite:///:memory:"
api_engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
APISessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=api_engine)


# ---------------------------------------------------------------------------
# Neon engine for service-level tests
# ---------------------------------------------------------------------------

_neon_engine = None
_NeonSessionLocal = None


def _get_neon_engine():
    global _neon_engine, _NeonSessionLocal
    if _neon_engine is None:
        _neon_engine = create_engine(settings.DATABASE_URL)
        _NeonSessionLocal = sessionmaker(bind=_neon_engine)
    return _neon_engine, _NeonSessionLocal


# ---------------------------------------------------------------------------
# Fixtures: API-level (SQLite)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=api_engine)
    yield
    Base.metadata.drop_all(bind=api_engine)


@pytest.fixture
def api_db():
    """Transactional SQLite session for API tests."""
    connection = api_engine.connect()
    transaction = connection.begin()
    session = APISessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(api_db):
    """FastAPI TestClient with DB override."""
    from app.main import app

    def override_get_db():
        yield api_db

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixtures: Service-level (Neon)
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Transactional Neon DB session for service tests."""
    engine, session_factory = _get_neon_engine()
    connection = engine.connect()
    transaction = connection.begin()
    session = session_factory(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def ceo_user(api_db):
    user = User(
        id=uuid4(),
        email="ceo@test.com",
        name="Test CEO",
        role="user",
        is_active=True,
    )
    api_db.add(user)
    api_db.flush()
    return user


@pytest.fixture
def admin_user(api_db):
    user = User(
        id=uuid4(),
        email="admin@test.com",
        name="Test Admin",
        role="user",
        is_active=True,
    )
    api_db.add(user)
    api_db.flush()
    return user


@pytest.fixture
def regular_user(api_db):
    user = User(
        id=uuid4(),
        email="user@test.com",
        name="Test User",
        role="user",
        is_active=True,
    )
    api_db.add(user)
    api_db.flush()
    return user


@pytest.fixture
def ceo_token(ceo_user):
    return create_access_token(data={"sub": str(ceo_user.id)})


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(data={"sub": str(admin_user.id)})


@pytest.fixture
def user_token(regular_user):
    return create_access_token(data={"sub": str(regular_user.id)})


@pytest.fixture
def ceo_headers(ceo_token):
    return {"Authorization": f"Bearer {ceo_token}"}


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# ---------------------------------------------------------------------------
# Neon DB user fixtures (for service tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def neon_user(db):
    user = User(
        id=uuid4(),
        email=f"test_{uuid4().hex[:8]}@example.com",
        name="Test User",
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def neon_ceo(db):
    user = User(
        id=uuid4(),
        email=f"ceo_{uuid4().hex[:8]}@example.com",
        name="Test CEO",
        role="ceo",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Sample data fixtures (API-level / SQLite)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_room(api_db):
    room = OfficeRoom(
        id=uuid4(),
        name="Test Room",
        description="A test office room",
        status=RoomStatus.AVAILABLE,
        visual_status=RoomVisualStatus.OFFLINE,
        room_type="workspace",
        capacity="1",
    )
    api_db.add(room)
    api_db.flush()
    return room


@pytest.fixture
def sample_agent(api_db, sample_room, ceo_user):
    agent = AIAgent(
        id=uuid4(),
        user_id=ceo_user.id,
        name="Test Agent",
        role="assistant",
        description="A test agent",
        status=AgentStatus.INACTIVE,
        lifecycle_status=LifecycleStatus.DRAFT,
        room_id=sample_room.id,
    )
    api_db.add(agent)
    api_db.flush()
    return agent


@pytest.fixture
def sample_tool(api_db):
    tool = AgentTool(
        id=uuid4(),
        name="test_tool",
        display_name="Test Tool",
        description="A test tool",
        category="general",
        risk_level="low",
        requires_approval=False,
        is_active=True,
    )
    api_db.add(tool)
    api_db.flush()
    return tool


@pytest.fixture
def sample_permission(api_db):
    perm = Permission(
        id=uuid4(),
        name="test.permission",
        description="Test permission",
        category="general",
        risk_level="low",
        default_status="allowed",
        is_active=True,
    )
    api_db.add(perm)
    api_db.flush()
    return perm


@pytest.fixture
def sample_integration(api_db):
    integration = Integration(
        id=uuid4(),
        name="test_integration",
        display_name="Test Integration",
        description="A test integration",
        auth_type="api_key",
        is_active=True,
    )
    api_db.add(integration)
    api_db.flush()
    return integration


@pytest.fixture
def sample_template(api_db):
    template = AgentTemplate(
        id=uuid4(),
        name="Test Template",
        role="assistant",
        description="A test template",
        default_goals=["Goal 1", "Goal 2"],
        default_rules=["Rule 1"],
        default_permissions=["test.permission"],
        default_tools=["test_tool"],
        is_active=True,
    )
    api_db.add(template)
    api_db.flush()
    return template


@pytest.fixture
def sample_task(api_db, sample_agent):
    task = Task(
        id=uuid4(),
        title="Test Task",
        description="A test task",
        status=TaskStatus.PENDING,
        task_type=TaskType.GENERAL,
        agent_id=sample_agent.id,
        priority=TaskPriority.MEDIUM,
    )
    api_db.add(task)
    api_db.flush()
    return task


@pytest.fixture
def sample_approval(api_db, sample_agent):
    approval = Approval(
        id=uuid4(),
        agent_id=sample_agent.id,
        action="send_email",
        risk_level="medium",
        status="pending",
        parameters={"to": "test@example.com", "subject": "Test"},
    )
    api_db.add(approval)
    api_db.flush()
    return approval


@pytest.fixture
def sample_notification(api_db, regular_user):
    notification = Notification(
        id=uuid4(),
        user_id=regular_user.id,
        type="info",
        title="Test Notification",
        message="This is a test notification",
        is_read=False,
        priority="low",
    )
    api_db.add(notification)
    api_db.flush()
    return notification


@pytest.fixture
def sample_risk_rule(api_db, sample_tool):
    rule = RiskRule(
        id=uuid4(),
        name="High Risk Email",
        description="Requires approval for email sending",
        action_name="send_email",
        risk_level="high",
        requires_approval=True,
        priority=10,
        is_active=True,
    )
    api_db.add(rule)
    api_db.flush()
    return rule


@pytest.fixture
def sample_knowledge(api_db, neon_user):
    source = KnowledgeSource(
        id=uuid4(),
        name="Test Knowledge",
        description="A test knowledge source",
        category="general",
        content="Python is a versatile programming language.",
        source_type="text",
        status=KnowledgeStatus.ACTIVE.value,
        chunk_count="0",
        created_by=neon_user.id,
    )
    api_db.add(source)
    api_db.flush()
    return source


@pytest.fixture
def sample_audit_log(api_db):
    log = AuditLog(
        id=uuid4(),
        action="test.action",
        resource_type="test",
        details={"key": "value"},
    )
    api_db.add(log)
    api_db.flush()
    return log


# ---------------------------------------------------------------------------
# Neon DB fixtures (for service-level tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def neon_agent(db, neon_user):
    agent = AIAgent(
        id=uuid4(),
        name="Neon Test Agent",
        role="assistant",
        status="inactive",
        lifecycle_status="draft",
    )
    db.add(agent)
    db.flush()
    return agent


@pytest.fixture
def neon_room(db):
    room = OfficeRoom(
        id=uuid4(),
        name="Neon Test Room",
        description="A test room",
        status="available",
        visual_status="offline",
        room_type="workspace",
        capacity="1",
    )
    db.add(room)
    db.flush()
    return room


@pytest.fixture
def neon_tool(db):
    tool = AgentTool(
        id=uuid4(),
        name="neon_test_tool",
        display_name="Neon Test Tool",
        description="A test tool",
        category="general",
        risk_level="low",
        requires_approval=False,
        is_active=True,
    )
    db.add(tool)
    db.flush()
    return tool


@pytest.fixture
def neon_permission(db):
    perm = Permission(
        id=uuid4(),
        name="neon.test.permission",
        description="Neon test permission",
        category="general",
        risk_level="low",
        default_status="allowed",
        is_active=True,
    )
    db.add(perm)
    db.flush()
    return perm


@pytest.fixture
def neon_integration(db):
    integration = Integration(
        id=uuid4(),
        name="neon_test_integration",
        display_name="Neon Test Integration",
        description="A test integration",
        auth_type="api_key",
        is_active=True,
    )
    db.add(integration)
    db.flush()
    return integration


@pytest.fixture
def neon_task(db, neon_agent):
    task = Task(
        id=uuid4(),
        title="Neon Test Task",
        description="A test task",
        status="pending",
        task_type="general",
        agent_id=neon_agent.id,
        priority="medium",
    )
    db.add(task)
    db.flush()
    return task


@pytest.fixture
def neon_approval(db, neon_agent):
    approval = Approval(
        id=uuid4(),
        agent_id=neon_agent.id,
        action="send_email",
        risk_level="medium",
        status="pending",
        parameters={"to": "test@example.com"},
    )
    db.add(approval)
    db.flush()
    return approval


@pytest.fixture
def neon_notification(db, neon_user):
    notification = Notification(
        id=uuid4(),
        user_id=neon_user.id,
        type="info",
        title="Neon Test Notification",
        message="Test",
        is_read=False,
        priority="low",
    )
    db.add(notification)
    db.flush()
    return notification


@pytest.fixture
def neon_knowledge(db, neon_user):
    source = KnowledgeSource(
        id=uuid4(),
        name="Neon Test Knowledge",
        description="Test",
        category="general",
        content="Python is a versatile language for web development and data science.",
        source_type="text",
        status="active",
        chunk_count="0",
        created_by=neon_user.id,
    )
    db.add(source)
    db.flush()
    return source


@pytest.fixture
def neon_email_account(db, neon_user):
    account = EmailAccount(
        id=uuid4(),
        user_id=neon_user.id,
        email_address="test@company.com",
        imap_host="imap.company.com",
        imap_port=993,
        imap_username="test@company.com",
        imap_password=encrypt_field("test_pass"),
        smtp_host="smtp.company.com",
        smtp_port=465,
        smtp_username="test@company.com",
        smtp_password=encrypt_field("test_pass"),
        is_active=True,
        sync_frequency_minutes=5,
    )
    db.add(account)
    db.flush()
    return account


@pytest.fixture
def mock_embedding_provider():
    """Mock embedding provider that returns deterministic fake embeddings."""
    dim = settings.EMBEDDING_DIMENSIONS

    provider = AsyncMock()
    provider.provider_name = "mock"
    provider.default_model = "mock-embed-v1"
    provider.default_dimensions = dim

    async def _embed_texts(texts, model=None, dimensions=None):
        from app.services.embedding_providers.base import EmbeddingResult
        import hashlib

        target_dim = dimensions or dim
        embeddings = []
        for text in texts:
            h = hashlib.md5(text.encode()).hexdigest()
            vec = []
            for i in range(target_dim):
                byte_idx = i % (len(h) // 2)
                hex_pair = h[byte_idx * 2:byte_idx * 2 + 2]
                vec.append(float(int(hex_pair, 16)) / 255.0)
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            embeddings.append(vec)

        return EmbeddingResult(
            embeddings=embeddings,
            model=model or "mock-embed-v1",
            dimensions=target_dim,
            usage={"total_tokens": sum(len(t.split()) for t in texts)},
        )

    provider.embed_texts = AsyncMock(side_effect=_embed_texts)

    async def _embed_query(text, model=None):
        result = await _embed_texts([text])
        return result.embeddings[0]

    provider.embed_query = AsyncMock(side_effect=_embed_query)

    return provider
