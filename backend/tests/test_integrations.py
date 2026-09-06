import pytest
from uuid import uuid4


class TestIntegrationCRUD:
    def test_create_integration(self, client, ceo_headers):
        payload = {
            "name": "slack",
            "display_name": "Slack",
            "auth_type": "oauth2",
            "description": "Team messaging",
            "is_active": True,
        }
        response = client.post("/api/v1/integrations/", json=payload, headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "slack"
        assert data["display_name"] == "Slack"
        assert data["auth_type"] == "oauth2"
        assert data["is_active"] is True

    def test_list_integrations_empty(self, client, ceo_headers):
        response = client.get("/api/v1/integrations/", headers=ceo_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_integrations_after_create(self, client, ceo_headers):
        payload = {
            "name": "github",
            "display_name": "GitHub",
            "auth_type": "oauth2",
        }
        client.post("/api/v1/integrations/", json=payload, headers=ceo_headers)

        response = client.get("/api/v1/integrations/", headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "github"

    def test_create_integration_returns_401_without_auth(self, client):
        payload = {
            "name": "slack",
            "display_name": "Slack",
            "auth_type": "oauth2",
        }
        response = client.post("/api/v1/integrations/", json=payload)
        assert response.status_code == 401

    def test_get_integration_by_id(self, client, ceo_headers):
        payload = {
            "name": "jira",
            "display_name": "Jira",
            "auth_type": "api_key",
        }
        create_resp = client.post("/api/v1/integrations/", json=payload, headers=ceo_headers)
        integration_id = create_resp.json()["id"]

        response = client.get(
            f"/api/v1/integrations/{integration_id}",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "jira"

    def test_get_nonexistent_integration_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/integrations/{fake_id}",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_create_multiple_integrations(self, client, ceo_headers):
        names = ["slack", "github", "jira"]
        for name in names:
            payload = {
                "name": name,
                "display_name": name.title(),
                "auth_type": "oauth2",
            }
            resp = client.post("/api/v1/integrations/", json=payload, headers=ceo_headers)
            assert resp.status_code == 200

        response = client.get("/api/v1/integrations/", headers=ceo_headers)
        assert response.status_code == 200
        assert len(response.json()) == 3


class TestIntegrationAccount:
    def test_connect_account(self, client, ceo_headers, sample_integration):
        response = client.post(
            f"/api/v1/integrations/accounts/connect",
            params={"integration_id": str(sample_integration.id)},
            json={"credentials": {"api_key": "test123"}, "display_name": "My Account"},
            headers=ceo_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "connected"
        assert data["display_name"] == "My Account"
        assert data["integration_id"] == str(sample_integration.id)

    def test_list_user_accounts_empty(self, client, ceo_headers):
        response = client.get("/api/v1/integrations/accounts/", headers=ceo_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_user_accounts_after_connect(self, client, ceo_headers, sample_integration):
        client.post(
            "/api/v1/integrations/accounts/connect",
            params={"integration_id": str(sample_integration.id)},
            json={"credentials": {"api_key": "test123"}},
            headers=ceo_headers,
        )

        response = client.get("/api/v1/integrations/accounts/", headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "connected"

    def test_disconnect_account(self, client, ceo_headers, sample_integration):
        client.post(
            "/api/v1/integrations/accounts/connect",
            params={"integration_id": str(sample_integration.id)},
            json={"credentials": {"api_key": "test123"}},
            headers=ceo_headers,
        )

        response = client.post(
            "/api/v1/integrations/accounts/disconnect",
            params={"integration_id": str(sample_integration.id)},
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert response.json()["detail"] == "Integration disconnected"

    def test_disconnect_nonexistent_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        response = client.post(
            "/api/v1/integrations/accounts/disconnect",
            params={"integration_id": str(fake_id)},
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_connect_account_returns_401_without_auth(self, client, sample_integration):
        response = client.post(
            "/api/v1/integrations/accounts/connect",
            params={"integration_id": str(sample_integration.id)},
            json={"credentials": {"api_key": "test123"}},
        )
        assert response.status_code == 401

    def test_connect_then_disconnect_flow(self, client, ceo_headers, sample_integration):
        connect_resp = client.post(
            "/api/v1/integrations/accounts/connect",
            params={"integration_id": str(sample_integration.id)},
            json={"credentials": {"api_key": "key123"}, "display_name": "Flow Test"},
            headers=ceo_headers,
        )
        assert connect_resp.status_code == 201

        accounts_resp = client.get("/api/v1/integrations/accounts/", headers=ceo_headers)
        assert len(accounts_resp.json()) == 1

        disconnect_resp = client.post(
            "/api/v1/integrations/accounts/disconnect",
            params={"integration_id": str(sample_integration.id)},
            headers=ceo_headers,
        )
        assert disconnect_resp.status_code == 200

        accounts_resp = client.get("/api/v1/integrations/accounts/", headers=ceo_headers)
        assert len(accounts_resp.json()) == 0


class TestAgentIntegrationAssignment:
    def test_assign_integration_to_agent(self, client, ceo_headers, sample_agent, sample_integration):
        response = client.post(
            f"/api/v1/integrations/agent/{sample_agent.id}/assign",
            params={"integration_id": str(sample_integration.id)},
            json=["read", "write"],
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["detail"] == "Integration assigned to agent"
        assert "id" in data

    def test_remove_integration_from_agent(self, client, ceo_headers, sample_agent, sample_integration):
        client.post(
            f"/api/v1/integrations/agent/{sample_agent.id}/assign",
            params={"integration_id": str(sample_integration.id)},
            json=["read"],
            headers=ceo_headers,
        )

        response = client.delete(
            f"/api/v1/integrations/agent/{sample_agent.id}/remove",
            params={"integration_id": str(sample_integration.id)},
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert response.json()["detail"] == "Integration removed from agent"

    def test_remove_nonexistent_assignment_returns_404(self, client, ceo_headers, sample_agent, sample_integration):
        response = client.delete(
            f"/api/v1/integrations/agent/{sample_agent.id}/remove",
            params={"integration_id": str(sample_integration.id)},
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_assign_nonexistent_agent_returns_404(self, client, ceo_headers, sample_integration):
        fake_agent_id = uuid4()
        response = client.post(
            f"/api/v1/integrations/agent/{fake_agent_id}/assign",
            params={"integration_id": str(sample_integration.id)},
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_assign_nonexistent_integration_returns_404(self, client, ceo_headers, sample_agent):
        fake_int_id = uuid4()
        response = client.post(
            f"/api/v1/integrations/agent/{sample_agent.id}/assign",
            params={"integration_id": str(fake_int_id)},
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_assign_returns_401_without_auth(self, client, sample_agent, sample_integration):
        response = client.post(
            f"/api/v1/integrations/agent/{sample_agent.id}/assign",
            params={"integration_id": str(sample_integration.id)},
        )
        assert response.status_code == 401

    def test_get_agent_integrations(self, client, ceo_headers, sample_agent, sample_integration):
        client.post(
            f"/api/v1/integrations/agent/{sample_agent.id}/assign",
            params={"integration_id": str(sample_integration.id)},
            json=["send_messages"],
            headers=ceo_headers,
        )

        response = client.get(
            f"/api/v1/integrations/agent/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_integration.name


class TestIntegrationAccountStatus:
    def test_get_account_status(self, client, ceo_headers, sample_integration):
        connect_resp = client.post(
            "/api/v1/integrations/accounts/connect",
            params={"integration_id": str(sample_integration.id)},
            json={"credentials": {"api_key": "test123"}},
            headers=ceo_headers,
        )
        account_id = connect_resp.json()["id"]

        response = client.get(
            f"/api/v1/integrations/accounts/{account_id}/status",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert "provider_available" in data

    def test_get_status_nonexistent_account_returns_404(self, client, ceo_headers):
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/integrations/accounts/{fake_id}/status",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_get_status_returns_401_without_auth(self, client, sample_integration):
        connect_resp = client.post(
            "/api/v1/integrations/accounts/connect",
            params={"integration_id": str(sample_integration.id)},
            json={"credentials": {"api_key": "test123"}},
        )
        assert connect_resp.status_code == 401

    def test_get_account_status_after_disconnect(self, client, ceo_headers, sample_integration):
        connect_resp = client.post(
            "/api/v1/integrations/accounts/connect",
            params={"integration_id": str(sample_integration.id)},
            json={"credentials": {"api_key": "test123"}},
            headers=ceo_headers,
        )
        account_id = connect_resp.json()["id"]

        client.post(
            "/api/v1/integrations/accounts/disconnect",
            params={"integration_id": str(sample_integration.id)},
            headers=ceo_headers,
        )

        response = client.get(
            f"/api/v1/integrations/accounts/{account_id}/status",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disconnected"

    def test_account_status_shows_connected_before_disconnect(self, client, ceo_headers, sample_integration):
        connect_resp = client.post(
            "/api/v1/integrations/accounts/connect",
            params={"integration_id": str(sample_integration.id)},
            json={"credentials": {"api_key": "abc"}},
            headers=ceo_headers,
        )
        account_id = connect_resp.json()["id"]

        status_resp = client.get(
            f"/api/v1/integrations/accounts/{account_id}/status",
            headers=ceo_headers,
        )
        assert status_resp.json()["status"] == "connected"

        client.post(
            "/api/v1/integrations/accounts/disconnect",
            params={"integration_id": str(sample_integration.id)},
            headers=ceo_headers,
        )

        status_resp = client.get(
            f"/api/v1/integrations/accounts/{account_id}/status",
            headers=ceo_headers,
        )
        assert status_resp.json()["status"] == "disconnected"
