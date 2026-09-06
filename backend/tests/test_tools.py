"""Tests for Tool CRUD, tool actions, and tool execution validation."""
import pytest
from unittest.mock import patch
from uuid import uuid4

from app.models.tool import AgentTool
from app.models.tool_action import ToolAction
from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.models.agent_tool_assignment import AgentToolAssignment
from app.services.tool_service import ToolService
from app.services.tool_execution_service import ToolExecutionService


# ------------------------------------------------------------------
# TestToolCRUD — Create, read, update, delete tools via API
# ------------------------------------------------------------------

class TestToolCRUD:
    def test_list_tools_empty(self, client, ceo_headers):
        resp = client.get("/api/v1/tools/", headers=ceo_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_tool(self, client, ceo_headers):
        payload = {
            "name": "email_writer",
            "display_name": "Email Writer",
            "description": "Writes emails",
            "category": "communication",
            "risk_level": "low",
            "requires_approval": False,
            "is_active": True,
        }
        resp = client.post("/api/v1/tools/", json=payload, headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "email_writer"
        assert data["display_name"] == "Email Writer"
        assert data["category"] == "communication"
        assert "id" in data

    def test_create_tool_minimal_fields(self, client, ceo_headers):
        payload = {
            "name": "minimal_tool",
            "display_name": "Minimal",
        }
        resp = client.post("/api/v1/tools/", json=payload, headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "minimal_tool"
        assert data["category"] == "general"
        assert data["risk_level"] == "low"
        assert data["is_active"] is True

    def test_get_tool_by_id(self, client, ceo_headers, sample_tool):
        resp = client.get(f"/api/v1/tools/{sample_tool.id}", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == sample_tool.name
        assert data["id"] == str(sample_tool.id)

    def test_get_tool_not_found(self, client, ceo_headers):
        resp = client.get(f"/api/v1/tools/{uuid4()}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_update_tool(self, client, ceo_headers, sample_tool):
        payload = {
            "display_name": "Updated Tool",
            "risk_level": "high",
            "requires_approval": True,
        }
        resp = client.put(f"/api/v1/tools/{sample_tool.id}", json=payload, headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "Updated Tool"
        assert data["risk_level"] == "high"
        assert data["requires_approval"] is True

    def test_update_tool_partial(self, client, ceo_headers, sample_tool):
        resp = client.put(
            f"/api/v1/tools/{sample_tool.id}",
            json={"display_name": "Only Name Changed"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Only Name Changed"
        assert resp.json()["risk_level"] == sample_tool.risk_level

    def test_update_tool_not_found(self, client, ceo_headers):
        resp = client.put(
            f"/api/v1/tools/{uuid4()}",
            json={"display_name": "Ghost"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_delete_tool(self, client, ceo_headers, sample_tool):
        resp = client.delete(f"/api/v1/tools/{sample_tool.id}", headers=ceo_headers)
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Tool deleted"
        get_resp = client.get(f"/api/v1/tools/{sample_tool.id}", headers=ceo_headers)
        assert get_resp.status_code == 404

    def test_delete_tool_not_found(self, client, ceo_headers):
        resp = client.delete(f"/api/v1/tools/{uuid4()}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_list_tools_after_create(self, client, ceo_headers):
        client.post(
            "/api/v1/tools/",
            json={"name": "tool_a", "display_name": "Tool A"},
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/tools/",
            json={"name": "tool_b", "display_name": "Tool B"},
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/tools/", headers=ceo_headers)
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert "tool_a" in names
        assert "tool_b" in names

    def test_list_tools_active_only(self, client, ceo_headers):
        client.post(
            "/api/v1/tools/",
            json={"name": "active_t", "display_name": "Active", "is_active": True},
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/tools/",
            json={"name": "inactive_t", "display_name": "Inactive", "is_active": False},
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/tools/?active_only=true", headers=ceo_headers)
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert "active_t" in names
        assert "inactive_t" not in names

    def test_list_tools_filter_by_category(self, client, ceo_headers):
        client.post(
            "/api/v1/tools/",
            json={"name": "comm_t", "display_name": "Comm", "category": "communication"},
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/tools/",
            json={"name": "data_t", "display_name": "Data", "category": "data"},
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/tools/?category=communication", headers=ceo_headers)
        assert resp.status_code == 200
        assert all(t["category"] == "communication" for t in resp.json())

    def test_tool_categories_endpoint(self, client, ceo_headers):
        client.post(
            "/api/v1/tools/",
            json={"name": "cat_a", "display_name": "A", "category": "alpha"},
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/tools/",
            json={"name": "cat_b", "display_name": "B", "category": "beta"},
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/tools/categories", headers=ceo_headers)
        assert resp.status_code == 200
        categories = resp.json()
        assert "alpha" in categories
        assert "beta" in categories


# ------------------------------------------------------------------
# TestToolActions — Create tool actions, verify they link to tools
# ------------------------------------------------------------------

class TestToolActions:
    def test_create_tool_action_via_service(self, db, neon_tool):
        service = ToolService(db)
        action = ToolAction(
            tool_id=neon_tool.id,
            name="send_email",
            display_name="Send Email",
            description="Send an email message",
            risk_level="low",
            requires_approval=False,
            is_active=True,
        )
        db.add(action)
        db.flush()
        assert action.id is not None
        assert action.tool_id == neon_tool.id
        assert action.name == "send_email"

    def test_tool_action_linked_to_tool(self, db, neon_tool):
        action = ToolAction(
            tool_id=neon_tool.id,
            name="read_email",
            display_name="Read Email",
            risk_level="low",
            requires_approval=False,
            is_active=True,
        )
        db.add(action)
        db.flush()
        service = ToolService(db)
        result = service.get_tool_with_actions(neon_tool.id)
        assert result is not None
        action_names = [a.name for a in result["actions"]]
        assert "read_email" in action_names

    def test_multiple_actions_per_tool(self, db, neon_tool):
        for i, name in enumerate(["action_1", "action_2", "action_3"]):
            action = ToolAction(
                tool_id=neon_tool.id,
                name=name,
                display_name=f"Action {i+1}",
                risk_level="low",
                requires_approval=False,
                is_active=True,
            )
            db.add(action)
        db.flush()
        service = ToolService(db)
        result = service.get_tool_with_actions(neon_tool.id)
        assert len(result["actions"]) == 3

    def test_action_risk_level_stored(self, db, neon_tool):
        action = ToolAction(
            tool_id=neon_tool.id,
            name="risky_action",
            display_name="Risky Action",
            risk_level="critical",
            requires_approval=True,
            is_active=True,
        )
        db.add(action)
        db.flush()
        service = ToolService(db)
        result = service.get_tool_with_actions(neon_tool.id)
        risky = [a for a in result["actions"] if a.name == "risky_action"][0]
        assert risky.risk_level == "critical"
        assert risky.requires_approval is True

    def test_inactive_action_not_returned(self, db, neon_tool):
        action = ToolAction(
            tool_id=neon_tool.id,
            name="disabled_action",
            display_name="Disabled",
            risk_level="low",
            requires_approval=False,
            is_active=False,
        )
        db.add(action)
        db.flush()
        service = ToolService(db)
        result = service.get_tool_with_actions(neon_tool.id)
        names = [a.name for a in result["actions"]]
        assert "disabled_action" not in names


# ------------------------------------------------------------------
# TestToolAccessCheck — check_tool_access returns tuples
# ------------------------------------------------------------------

class TestToolAccessCheck:
    def _make_active_agent(self, db, tools="test_tool"):
        agent = AIAgent(
            id=uuid4(),
            name="Active Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE,
            tools=tools,
        )
        db.add(agent)
        db.flush()
        db.refresh(agent)
        return agent

    def test_access_granted(self, db, neon_tool):
        agent = self._make_active_agent(db, tools="neon_test_tool")
        service = ToolExecutionService(db)
        allowed, reason, risk_level = service.check_tool_access(agent.id, "neon_test_tool")
        assert allowed is True
        assert "granted" in reason.lower()
        assert risk_level == neon_tool.risk_level

    def test_agent_not_found(self, db, neon_tool):
        service = ToolExecutionService(db)
        allowed, reason, risk_level = service.check_tool_access(uuid4(), "neon_test_tool")
        assert allowed is False
        assert "not found" in reason.lower()
        assert risk_level is None

    def test_agent_not_active(self, db, neon_tool):
        agent = AIAgent(
            id=uuid4(),
            name="Inactive Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.DRAFT,
            tools="neon_test_tool",
        )
        db.add(agent)
        db.flush()
        db.refresh(agent)
        service = ToolExecutionService(db)
        allowed, reason, _ = service.check_tool_access(agent.id, "neon_test_tool")
        assert allowed is False
        assert "not active" in reason.lower()

    def test_tool_not_assigned(self, db, neon_tool):
        agent = self._make_active_agent(db, tools="other_tool")
        service = ToolExecutionService(db)
        allowed, reason, _ = service.check_tool_access(agent.id, "neon_test_tool")
        assert allowed is False
        assert "not assigned" in reason.lower()

    def test_tool_not_found(self, db):
        agent = self._make_active_agent(db, tools="nonexistent_tool")
        service = ToolExecutionService(db)
        allowed, reason, _ = service.check_tool_access(agent.id, "nonexistent_tool")
        assert allowed is False
        assert "not found" in reason.lower()

    def test_tool_disabled(self, db, neon_tool):
        agent = self._make_active_agent(db, tools="neon_test_tool")
        neon_tool.is_active = False
        db.flush()
        service = ToolExecutionService(db)
        allowed, reason, _ = service.check_tool_access(agent.id, "neon_test_tool")
        assert allowed is False
        assert "disabled" in reason.lower()

    def test_empty_tools_string(self, db):
        agent = AIAgent(
            id=uuid4(),
            name="No Tools Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE,
            tools="",
        )
        db.add(agent)
        db.flush()
        db.refresh(agent)
        service = ToolExecutionService(db)
        allowed, reason, _ = service.check_tool_access(agent.id, "some_tool")
        assert allowed is False

    def test_none_tools_field(self, db):
        agent = AIAgent(
            id=uuid4(),
            name="Null Tools Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE,
            tools=None,
        )
        db.add(agent)
        db.flush()
        db.refresh(agent)
        service = ToolExecutionService(db)
        allowed, reason, _ = service.check_tool_access(agent.id, "some_tool")
        assert allowed is False

    def test_action_access_granted(self, db, neon_tool):
        agent = self._make_active_agent(db, tools="neon_test_tool")
        action = ToolAction(
            tool_id=neon_tool.id,
            name="send",
            display_name="Send",
            risk_level="medium",
            requires_approval=False,
            is_active=True,
        )
        db.add(action)
        db.flush()
        service = ToolExecutionService(db)
        allowed, reason, risk_level = service.check_action_access(agent.id, "neon_test_tool", "send")
        assert allowed is True
        assert risk_level == "medium"

    def test_action_not_found(self, db, neon_tool):
        agent = self._make_active_agent(db, tools="neon_test_tool")
        service = ToolExecutionService(db)
        allowed, reason, _ = service.check_action_access(agent.id, "neon_test_tool", "nonexistent_action")
        assert allowed is False
        assert "not found" in reason.lower()

    def test_action_inactive(self, db, neon_tool):
        agent = self._make_active_agent(db, tools="neon_test_tool")
        action = ToolAction(
            tool_id=neon_tool.id,
            name="old_action",
            display_name="Old",
            risk_level="low",
            requires_approval=False,
            is_active=False,
        )
        db.add(action)
        db.flush()
        service = ToolExecutionService(db)
        allowed, reason, _ = service.check_action_access(agent.id, "neon_test_tool", "old_action")
        assert allowed is False
        assert "not found" in reason.lower()


# ------------------------------------------------------------------
# TestToolValidation — GET /api/v1/tools/validate/{agent_id}/{tool_name}
# ------------------------------------------------------------------

class TestToolValidation:
    def _setup_active_agent(self, api_db, sample_tool):
        agent = AIAgent(
            id=uuid4(),
            name="Validator Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE,
        )
        api_db.add(agent)
        api_db.flush()
        assignment = AgentToolAssignment(
            agent_id=agent.id,
            tool_id=sample_tool.id,
            is_enabled=True,
        )
        api_db.add(assignment)
        api_db.flush()
        return agent

    def test_validate_tool_access_granted(self, client, ceo_headers, api_db, sample_tool):
        agent = self._setup_active_agent(api_db, sample_tool)
        resp = client.get(
            f"/api/v1/tools/validate/{agent.id}/{sample_tool.name}",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_access"] is True
        assert "granted" in data["message"].lower()

    def test_validate_tool_not_assigned(self, client, ceo_headers, api_db, sample_tool):
        agent = AIAgent(
            id=uuid4(),
            name="Unassigned Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE,
        )
        api_db.add(agent)
        api_db.flush()
        resp = client.get(
            f"/api/v1/tools/validate/{agent.id}/{sample_tool.name}",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_access"] is False
        assert "not assigned" in data["message"].lower()

    def test_validate_tool_agent_not_active(self, client, ceo_headers, api_db, sample_tool):
        agent = AIAgent(
            id=uuid4(),
            name="Draft Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.DRAFT,
        )
        api_db.add(agent)
        api_db.flush()
        resp = client.get(
            f"/api/v1/tools/validate/{agent.id}/{sample_tool.name}",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_access"] is False

    def test_validate_tool_agent_not_found(self, client, ceo_headers, sample_tool):
        resp = client.get(
            f"/api/v1/tools/validate/{uuid4()}/{sample_tool.name}",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_access"] is False
        assert "not found" in data["message"].lower()

    def test_validate_tool_not_found(self, client, ceo_headers, api_db):
        agent = AIAgent(
            id=uuid4(),
            name="Toolless Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE,
        )
        api_db.add(agent)
        api_db.flush()
        resp = client.get(
            f"/api/v1/tools/validate/{agent.id}/ghost_tool",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_access"] is False

    def test_validate_tool_with_action(self, client, ceo_headers, api_db, sample_tool):
        agent = self._setup_active_agent(api_db, sample_tool)
        action = ToolAction(
            tool_id=sample_tool.id,
            name="read",
            display_name="Read",
            risk_level="low",
            requires_approval=False,
            is_active=True,
        )
        api_db.add(action)
        api_db.flush()
        resp = client.get(
            f"/api/v1/tools/validate/{agent.id}/{sample_tool.name}?action_name=read",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["has_access"] is True

    def test_validate_tool_with_invalid_action(self, client, ceo_headers, api_db, sample_tool):
        agent = self._setup_active_agent(api_db, sample_tool)
        resp = client.get(
            f"/api/v1/tools/validate/{agent.id}/{sample_tool.name}?action_name=delete_everything",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["has_access"] is False

    def test_validate_requires_auth(self, client, api_db, sample_tool):
        agent = AIAgent(
            id=uuid4(),
            name="No Auth Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE,
        )
        api_db.add(agent)
        api_db.flush()
        resp = client.get(
            f"/api/v1/tools/validate/{agent.id}/{sample_tool.name}",
        )
        assert resp.status_code == 401


# ------------------------------------------------------------------
# Service-level tests (Neon DB)
# ------------------------------------------------------------------

class TestToolServiceNeon:
    def test_create_and_get_tool(self, db):
        service = ToolService(db)
        from app.schemas.tool import ToolCreate
        tool = service.create_tool(ToolCreate(
            name="service_tool",
            display_name="Service Tool",
            category="integration",
            risk_level="medium",
        ))
        assert tool.id is not None
        fetched = service.get_tool(tool.id)
        assert fetched.name == "service_tool"

    def test_update_tool_via_service(self, db):
        service = ToolService(db)
        from app.schemas.tool import ToolCreate, ToolUpdate
        tool = service.create_tool(ToolCreate(name="upd_tool", display_name="Upd"))
        updated = service.update_tool(tool.id, ToolUpdate(display_name="Updated"))
        assert updated.display_name == "Updated"

    def test_delete_tool_via_service(self, db):
        service = ToolService(db)
        from app.schemas.tool import ToolCreate
        tool = service.create_tool(ToolCreate(name="del_tool", display_name="Del"))
        assert service.delete_tool(tool.id) is True
        assert service.get_tool(tool.id) is None

    def test_delete_nonexistent_tool(self, db):
        service = ToolService(db)
        assert service.delete_tool(uuid4()) is False

    def test_get_tool_by_name(self, db):
        service = ToolService(db)
        from app.schemas.tool import ToolCreate
        service.create_tool(ToolCreate(name="named_tool", display_name="Named"))
        found = service.get_tool_by_name("named_tool")
        assert found is not None
        assert found.name == "named_tool"

    def test_get_tools_by_category(self, db):
        service = ToolService(db)
        from app.schemas.tool import ToolCreate
        service.create_tool(ToolCreate(name="cat_x", display_name="X", category="email"))
        service.create_tool(ToolCreate(name="cat_y", display_name="Y", category="email"))
        service.create_tool(ToolCreate(name="cat_z", display_name="Z", category="chat"))
        email_tools = service.get_tools_by_category("email")
        assert len(email_tools) >= 2
        assert all(t.category == "email" for t in email_tools)

    def test_get_tool_categories_distinct(self, db):
        service = ToolService(db)
        from app.schemas.tool import ToolCreate
        service.create_tool(ToolCreate(name="c1", display_name="C1", category="alpha"))
        service.create_tool(ToolCreate(name="c2", display_name="C2", category="beta"))
        cats = service.get_tool_categories()
        assert "alpha" in cats
        assert "beta" in cats
