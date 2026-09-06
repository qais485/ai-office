"""Tests for Permission CRUD, agent permissions, and permission checks."""
import pytest
from uuid import uuid4

from app.models.permission import Permission
from app.models.agent_permission import AgentPermission
from app.models.agent import AIAgent, AgentStatus, LifecycleStatus
from app.services.permission_service import PermissionService


# ------------------------------------------------------------------
# TestPermissionCRUD — Create, read, update, delete via API
# ------------------------------------------------------------------

class TestPermissionCRUD:
    def test_list_permissions_empty(self, client, ceo_headers):
        resp = client.get("/api/v1/permissions/", headers=ceo_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_permission(self, client, ceo_headers):
        payload = {
            "name": "email.send",
            "description": "Allow sending emails",
            "category": "email",
            "risk_level": "medium",
            "default_status": "approval_required",
            "is_active": True,
        }
        resp = client.post("/api/v1/permissions/", json=payload, headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "email.send"
        assert data["category"] == "email"
        assert data["risk_level"] == "medium"
        assert "id" in data

    def test_create_permission_duplicate_name(self, client, ceo_headers, sample_permission):
        payload = {
            "name": sample_permission.name,
            "description": "Duplicate",
            "category": "general",
        }
        resp = client.post("/api/v1/permissions/", json=payload, headers=ceo_headers)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_get_permission_by_id(self, client, ceo_headers, sample_permission):
        resp = client.get(f"/api/v1/permissions/{sample_permission.id}", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == sample_permission.name
        assert data["id"] == str(sample_permission.id)

    def test_get_permission_not_found(self, client, ceo_headers):
        resp = client.get(f"/api/v1/permissions/{uuid4()}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_update_permission(self, client, ceo_headers, sample_permission):
        payload = {
            "description": "Updated description",
            "risk_level": "high",
            "default_status": "denied",
        }
        resp = client.put(
            f"/api/v1/permissions/{sample_permission.id}",
            json=payload,
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated description"
        assert data["risk_level"] == "high"
        assert data["default_status"] == "denied"

    def test_update_permission_partial(self, client, ceo_headers, sample_permission):
        resp = client.put(
            f"/api/v1/permissions/{sample_permission.id}",
            json={"risk_level": "critical"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["risk_level"] == "critical"
        assert resp.json()["name"] == sample_permission.name

    def test_update_permission_not_found(self, client, ceo_headers):
        resp = client.put(
            f"/api/v1/permissions/{uuid4()}",
            json={"description": "Ghost"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_delete_permission(self, client, ceo_headers, sample_permission):
        resp = client.delete(f"/api/v1/permissions/{sample_permission.id}", headers=ceo_headers)
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Permission deleted"
        get_resp = client.get(f"/api/v1/permissions/{sample_permission.id}", headers=ceo_headers)
        assert get_resp.status_code == 404

    def test_delete_permission_not_found(self, client, ceo_headers):
        resp = client.delete(f"/api/v1/permissions/{uuid4()}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_list_permissions_after_create(self, client, ceo_headers):
        client.post(
            "/api/v1/permissions/",
            json={"name": "perm_a", "description": "A", "category": "general"},
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/permissions/",
            json={"name": "perm_b", "description": "B", "category": "email"},
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/permissions/", headers=ceo_headers)
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "perm_a" in names
        assert "perm_b" in names

    def test_list_permissions_active_only(self, client, ceo_headers):
        client.post(
            "/api/v1/permissions/",
            json={"name": "active_p", "category": "general", "is_active": True},
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/permissions/",
            json={"name": "inactive_p", "category": "general", "is_active": False},
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/permissions/?active_only=true", headers=ceo_headers)
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "active_p" in names
        assert "inactive_p" not in names

    def test_list_permissions_filter_by_category(self, client, ceo_headers):
        client.post(
            "/api/v1/permissions/",
            json={"name": "email_read", "category": "email"},
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/permissions/",
            json={"name": "chat_send", "category": "chat"},
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/permissions/?category=email", headers=ceo_headers)
        assert resp.status_code == 200
        assert all(p["category"] == "email" for p in resp.json())


# ------------------------------------------------------------------
# TestAgentPermissionGrant — Grant permissions to agents via API
# ------------------------------------------------------------------

class TestAgentPermissionGrant:
    def test_grant_permission_to_agent(self, client, ceo_headers, sample_agent, sample_permission):
        payload = {
            "permission_id": str(sample_permission.id),
            "access_level": "allowed",
            "notes": "Granted for testing",
        }
        resp = client.post(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            json=payload,
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == str(sample_agent.id)
        assert data["permission_id"] == str(sample_permission.id)
        assert data["access_level"] == "allowed"

    def test_grant_multiple_permissions(self, client, ceo_headers, sample_agent, api_db):
        perm1 = Permission(
            id=uuid4(), name="perm.multi1", category="general",
            risk_level="low", default_status="allowed", is_active=True,
        )
        perm2 = Permission(
            id=uuid4(), name="perm.multi2", category="email",
            risk_level="medium", default_status="allowed", is_active=True,
        )
        api_db.add_all([perm1, perm2])
        api_db.flush()

        for perm in [perm1, perm2]:
            resp = client.post(
                f"/api/v1/permissions/agent/{sample_agent.id}",
                json={"permission_id": str(perm.id), "access_level": "allowed"},
                headers=ceo_headers,
            )
            assert resp.status_code == 200

        resp = client.get(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        perm_names = [p["permission_name"] for p in resp.json()]
        assert "perm.multi1" in perm_names
        assert "perm.multi2" in perm_names

    def test_grant_updates_existing(self, client, ceo_headers, sample_agent, sample_permission):
        payload = {
            "permission_id": str(sample_permission.id),
            "access_level": "allowed",
        }
        client.post(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            json=payload,
            headers=ceo_headers,
        )
        update_payload = {
            "permission_id": str(sample_permission.id),
            "access_level": "denied",
            "notes": "Revoked",
        }
        resp = client.post(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            json=update_payload,
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["access_level"] == "denied"

    def test_grant_approval_required(self, client, ceo_headers, sample_agent, sample_permission):
        payload = {
            "permission_id": str(sample_permission.id),
            "access_level": "approval_required",
        }
        resp = client.post(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            json=payload,
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["access_level"] == "approval_required"

    def test_list_agent_permissions(self, client, ceo_headers, sample_agent, sample_permission):
        client.post(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            json={"permission_id": str(sample_permission.id), "access_level": "allowed"},
            headers=ceo_headers,
        )
        resp = client.get(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        perms = resp.json()
        assert len(perms) >= 1
        assert perms[0]["permission_name"] == sample_permission.name


# ------------------------------------------------------------------
# TestAgentPermissionRevoke — Revoke individual and all permissions
# ------------------------------------------------------------------

class TestAgentPermissionRevoke:
    def test_revoke_individual_permission(self, client, ceo_headers, sample_agent, sample_permission):
        client.post(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            json={"permission_id": str(sample_permission.id), "access_level": "allowed"},
            headers=ceo_headers,
        )
        resp = client.delete(
            f"/api/v1/permissions/agent/{sample_agent.id}/{sample_permission.id}",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Agent permission deleted"
        get_resp = client.get(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert get_resp.status_code == 200
        assert len(get_resp.json()) == 0

    def test_revoke_nonexistent_permission(self, client, ceo_headers, sample_agent):
        resp = client.delete(
            f"/api/v1/permissions/agent/{sample_agent.id}/{uuid4()}",
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_revoke_all_permissions(self, client, ceo_headers, sample_agent, api_db):
        perms = []
        for i in range(3):
            p = Permission(
                id=uuid4(), name=f"revoke_all_{i}", category="general",
                risk_level="low", default_status="allowed", is_active=True,
            )
            perms.append(p)
        api_db.add_all(perms)
        api_db.flush()

        for p in perms:
            client.post(
                f"/api/v1/permissions/agent/{sample_agent.id}",
                json={"permission_id": str(p.id), "access_level": "allowed"},
                headers=ceo_headers,
            )

        list_resp = client.get(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert len(list_resp.json()) == 3

        resp = client.post(
            f"/api/v1/permissions/agent/{sample_agent.id}/revoke-all",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "All agent permissions revoked"

        list_resp = client.get(
            f"/api/v1/permissions/agent/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert len(list_resp.json()) == 0

    def test_revoke_all_when_no_permissions(self, client, ceo_headers, sample_agent):
        resp = client.post(
            f"/api/v1/permissions/agent/{sample_agent.id}/revoke-all",
            headers=ceo_headers,
        )
        assert resp.status_code == 200


# ------------------------------------------------------------------
# TestPermissionCheck — POST /api/v1/permissions/check
# ------------------------------------------------------------------

class TestPermissionCheck:
    def _make_active_agent(self, api_db):
        agent = AIAgent(
            id=uuid4(),
            name="Check Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE,
        )
        api_db.add(agent)
        api_db.flush()
        return agent

    def test_check_permission_allowed(self, client, ceo_headers, api_db, sample_permission):
        agent = self._make_active_agent(api_db)
        client.post(
            f"/api/v1/permissions/agent/{agent.id}",
            json={"permission_id": str(sample_permission.id), "access_level": "allowed"},
            headers=ceo_headers,
        )
        resp = client.post(
            "/api/v1/permissions/check",
            json={"agent_id": str(agent.id), "permission_name": sample_permission.name},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_permission"] is True
        assert data["access_level"] == "allowed"
        assert data["requires_approval"] is False

    def test_check_permission_denied(self, client, ceo_headers, api_db, sample_permission):
        agent = self._make_active_agent(api_db)
        client.post(
            f"/api/v1/permissions/agent/{agent.id}",
            json={"permission_id": str(sample_permission.id), "access_level": "denied"},
            headers=ceo_headers,
        )
        resp = client.post(
            "/api/v1/permissions/check",
            json={"agent_id": str(agent.id), "permission_name": sample_permission.name},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_permission"] is False
        assert data["access_level"] == "denied"

    def test_check_permission_approval_required(self, client, ceo_headers, api_db, sample_permission):
        agent = self._make_active_agent(api_db)
        client.post(
            f"/api/v1/permissions/agent/{agent.id}",
            json={"permission_id": str(sample_permission.id), "access_level": "approval_required"},
            headers=ceo_headers,
        )
        resp = client.post(
            "/api/v1/permissions/check",
            json={"agent_id": str(agent.id), "permission_name": sample_permission.name},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_permission"] is True
        assert data["access_level"] == "approval_required"
        assert data["requires_approval"] is True

    def test_check_permission_not_granted(self, client, ceo_headers, api_db, sample_permission):
        agent = self._make_active_agent(api_db)
        resp = client.post(
            "/api/v1/permissions/check",
            json={"agent_id": str(agent.id), "permission_name": sample_permission.name},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_permission"] is False
        assert "not granted" in data["message"].lower()

    def test_check_permission_nonexistent_name(self, client, ceo_headers, api_db):
        agent = self._make_active_agent(api_db)
        resp = client.post(
            "/api/v1/permissions/check",
            json={"agent_id": str(agent.id), "permission_name": "no.such.perm"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_permission"] is False
        assert "not found" in data["message"].lower()

    def test_check_permission_agent_not_found(self, client, ceo_headers, sample_permission):
        resp = client.post(
            "/api/v1/permissions/check",
            json={"agent_id": str(uuid4()), "permission_name": sample_permission.name},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_permission"] is False
        assert "not found" in data["message"].lower()

    def test_check_permission_agent_inactive(self, client, ceo_headers, api_db, sample_permission):
        agent = AIAgent(
            id=uuid4(),
            name="Inactive Check Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.DRAFT,
        )
        api_db.add(agent)
        api_db.flush()
        client.post(
            f"/api/v1/permissions/agent/{agent.id}",
            json={"permission_id": str(sample_permission.id), "access_level": "allowed"},
            headers=ceo_headers,
        )
        resp = client.post(
            "/api/v1/permissions/check",
            json={"agent_id": str(agent.id), "permission_name": sample_permission.name},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_permission"] is False
        assert "not active" in data["message"].lower()


# ------------------------------------------------------------------
# TestPermissionCategories — GET /api/v1/permissions/categories
# ------------------------------------------------------------------

class TestPermissionCategories:
    def test_get_categories(self, client, ceo_headers, api_db):
        p1 = Permission(
            id=uuid4(), name="cat_test_1", category="email",
            risk_level="low", default_status="allowed", is_active=True,
        )
        p2 = Permission(
            id=uuid4(), name="cat_test_2", category="chat",
            risk_level="low", default_status="allowed", is_active=True,
        )
        p3 = Permission(
            id=uuid4(), name="cat_test_3", category="email",
            risk_level="low", default_status="allowed", is_active=True,
        )
        api_db.add_all([p1, p2, p3])
        api_db.flush()

        resp = client.get("/api/v1/permissions/categories", headers=ceo_headers)
        assert resp.status_code == 200
        categories = resp.json()
        assert "email" in categories
        assert "chat" in categories

    def test_categories_are_distinct(self, client, ceo_headers, api_db):
        for i in range(5):
            p = Permission(
                id=uuid4(), name=f"dup_cat_{i}", category="same_cat",
                risk_level="low", default_status="allowed", is_active=True,
            )
            api_db.add(p)
        api_db.flush()

        resp = client.get("/api/v1/permissions/categories", headers=ceo_headers)
        assert resp.status_code == 200
        categories = resp.json()
        assert categories.count("same_cat") == 1

    def test_categories_empty_when_no_permissions(self, client, ceo_headers):
        resp = client.get("/api/v1/permissions/categories", headers=ceo_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ------------------------------------------------------------------
# Service-level tests (Neon DB)
# ------------------------------------------------------------------

class TestPermissionServiceNeon:
    def _make_active_agent(self, db):
        agent = AIAgent(
            id=uuid4(),
            name="Neon Active Agent",
            role="assistant",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.ACTIVE,
        )
        db.add(agent)
        db.flush()
        db.refresh(agent)
        return agent

    def test_create_and_get_permission(self, db):
        perm = Permission(
            id=uuid4(),
            name=f"svc.perm.{uuid4().hex[:6]}",
            description="Service permission",
            category="integration",
            risk_level="medium",
            default_status="allowed",
            is_active=True,
        )
        db.add(perm)
        db.flush()
        db.refresh(perm)
        service = PermissionService(db)
        fetched = service.get_permission(perm.id)
        assert fetched.name == perm.name

    def test_get_permission_by_name(self, db):
        name = f"named.perm.{uuid4().hex[:6]}"
        perm = Permission(
            id=uuid4(), name=name, description="", category="general",
            risk_level="low", default_status="allowed", is_active=True,
        )
        db.add(perm)
        db.flush()
        service = PermissionService(db)
        found = service.get_permission_by_name(name)
        assert found is not None

    def test_update_permission_via_service(self, db):
        perm = Permission(
            id=uuid4(), name=f"upd.perm.{uuid4().hex[:6]}", description="old",
            category="general", risk_level="low", default_status="allowed", is_active=True,
        )
        db.add(perm)
        db.flush()
        db.refresh(perm)
        service = PermissionService(db)
        from app.schemas.permission import PermissionUpdate
        updated = service.update_permission(perm.id, PermissionUpdate(description="new"))
        assert updated.description == "new"

    def test_delete_permission_via_service(self, db):
        perm = Permission(
            id=uuid4(), name=f"del.perm.{uuid4().hex[:6]}", description="",
            category="general", risk_level="low", default_status="allowed", is_active=True,
        )
        db.add(perm)
        db.flush()
        db.refresh(perm)
        service = PermissionService(db)
        assert service.delete_permission(perm.id) is True
        assert service.get_permission(perm.id) is None

    def test_delete_nonexistent_permission(self, db):
        service = PermissionService(db)
        assert service.delete_permission(uuid4()) is False

    def test_get_permission_categories_distinct(self, db):
        for i, cat in enumerate(["alpha_svc", "beta_svc"]):
            p = Permission(
                id=uuid4(), name=f"cat_svc_{i}.{uuid4().hex[:6]}", category=cat,
                description="", risk_level="low", default_status="allowed", is_active=True,
            )
            db.add(p)
        db.flush()
        service = PermissionService(db)
        cats = service.get_permission_categories()
        assert "alpha_svc" in cats
        assert "beta_svc" in cats

    def test_set_agent_permission(self, db, neon_permission):
        agent = self._make_active_agent(db)
        service = PermissionService(db)
        from app.schemas.permission import AgentPermissionCreate
        ap = service.set_agent_permission(
            agent.id,
            AgentPermissionCreate(permission_id=neon_permission.id, access_level="allowed"),
            granted_by="test",
        )
        assert ap.agent_id == agent.id
        assert ap.permission_id == neon_permission.id
        assert ap.access_level == "allowed"

    def test_set_agent_permission_updates_existing(self, db, neon_permission):
        agent = self._make_active_agent(db)
        service = PermissionService(db)
        from app.schemas.permission import AgentPermissionCreate
        service.set_agent_permission(
            agent.id,
            AgentPermissionCreate(permission_id=neon_permission.id, access_level="allowed"),
        )
        updated = service.set_agent_permission(
            agent.id,
            AgentPermissionCreate(permission_id=neon_permission.id, access_level="denied"),
        )
        assert updated.access_level == "denied"

    def test_check_permission_allowed(self, db, neon_permission):
        agent = self._make_active_agent(db)
        service = PermissionService(db)
        from app.schemas.permission import AgentPermissionCreate
        service.set_agent_permission(
            agent.id,
            AgentPermissionCreate(permission_id=neon_permission.id, access_level="allowed"),
        )
        has_perm, access_level, msg = service.check_permission(agent.id, neon_permission.name)
        assert has_perm is True
        assert access_level == "allowed"

    def test_check_permission_denied(self, db, neon_permission):
        agent = self._make_active_agent(db)
        service = PermissionService(db)
        from app.schemas.permission import AgentPermissionCreate
        service.set_agent_permission(
            agent.id,
            AgentPermissionCreate(permission_id=neon_permission.id, access_level="denied"),
        )
        has_perm, access_level, msg = service.check_permission(agent.id, neon_permission.name)
        assert has_perm is False
        assert access_level == "denied"

    def test_check_permission_not_granted(self, db, neon_permission):
        agent = self._make_active_agent(db)
        service = PermissionService(db)
        has_perm, access_level, msg = service.check_permission(agent.id, neon_permission.name)
        assert has_perm is False
        assert "not granted" in msg.lower()

    def test_check_permission_nonexistent(self, db):
        agent = self._make_active_agent(db)
        service = PermissionService(db)
        has_perm, access_level, msg = service.check_permission(agent.id, "no.such.thing")
        assert has_perm is False
        assert "not found" in msg.lower()

    def test_delete_agent_permission(self, db, neon_permission):
        agent = self._make_active_agent(db)
        service = PermissionService(db)
        from app.schemas.permission import AgentPermissionCreate
        service.set_agent_permission(
            agent.id,
            AgentPermissionCreate(permission_id=neon_permission.id, access_level="allowed"),
        )
        assert service.delete_agent_permission(agent.id, neon_permission.id) is True
        assert service.delete_agent_permission(agent.id, neon_permission.id) is False

    def test_revoke_all_agent_permissions(self, db):
        agent = self._make_active_agent(db)
        service = PermissionService(db)
        from app.schemas.permission import PermissionCreate, AgentPermissionCreate
        for i in range(3):
            perm = Permission(
                id=uuid4(), name=f"revoke_svc_{i}.{uuid4().hex[:6]}", category="general",
                description="", risk_level="low", default_status="allowed", is_active=True,
            )
            db.add(perm)
            db.flush()
            db.refresh(perm)
            service.set_agent_permission(
                agent.id,
                AgentPermissionCreate(permission_id=perm.id, access_level="allowed"),
            )
        assert service.revoke_all_agent_permissions(agent.id) is True
        remaining = service.get_agent_permissions(agent.id)
        assert len(remaining) == 0
