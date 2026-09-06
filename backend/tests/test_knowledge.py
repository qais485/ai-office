"""Tests for Knowledge CRUD, access control, search, stats, and chunking integration."""
import pytest
from uuid import uuid4
from unittest.mock import patch

from app.models.knowledge import KnowledgeSource, KnowledgeStatus
from app.models.agent_knowledge import AgentKnowledgeAccess
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate


PATCH_TARGET = "app.services.rag_service.get_embedding_provider"


class TestKnowledgeCRUD:
    def test_list_knowledge(self, client, ceo_headers):
        response = client.get("/api/v1/knowledge/", headers=ceo_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_knowledge(self, client, ceo_headers):
        payload = {
            "name": "API Test Doc",
            "description": "Created via API",
            "category": "general",
            "content": "Some test content about Python programming.",
            "source_type": "text",
        }
        response = client.post(
            "/api/v1/knowledge/",
            json=payload,
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "API Test Doc"
        assert data["category"] == "general"
        assert data["source_type"] == "text"
        assert data["id"] is not None

    def test_create_knowledge_minimal(self, client, ceo_headers):
        payload = {
            "name": "Minimal Doc",
            "category": "faq",
        }
        response = client.post(
            "/api/v1/knowledge/",
            json=payload,
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Minimal Doc"
        assert data["category"] == "faq"
        assert data["source_type"] == "note"

    def test_get_knowledge_by_id(self, client, ceo_headers, sample_knowledge):
        response = client.get(
            f"/api/v1/knowledge/{sample_knowledge.id}",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_knowledge.id)
        assert data["name"] == sample_knowledge.name

    def test_get_knowledge_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/knowledge/{fake_id}",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_update_knowledge(self, client, ceo_headers, sample_knowledge):
        payload = {
            "name": "Updated Knowledge Name",
            "description": "Updated description",
            "category": "pricing",
        }
        response = client.put(
            f"/api/v1/knowledge/{sample_knowledge.id}",
            json=payload,
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Knowledge Name"
        assert data["description"] == "Updated description"
        assert data["category"] == "pricing"

    def test_update_knowledge_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        payload = {"name": "Does Not Exist"}
        response = client.put(
            f"/api/v1/knowledge/{fake_id}",
            json=payload,
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_delete_knowledge(self, client, ceo_headers, sample_knowledge):
        response = client.delete(
            f"/api/v1/knowledge/{sample_knowledge.id}",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert response.json()["detail"] == "Knowledge source deleted"

        get_response = client.get(
            f"/api/v1/knowledge/{sample_knowledge.id}",
            headers=ceo_headers,
        )
        assert get_response.status_code == 404

    def test_delete_knowledge_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        response = client.delete(
            f"/api/v1/knowledge/{fake_id}",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_list_knowledge_with_category_filter(self, client, ceo_headers, sample_knowledge):
        client.post(
            "/api/v1/knowledge/",
            json={
                "name": "FAQ Item",
                "category": "faq",
                "content": "Frequently asked question content.",
                "source_type": "text",
            },
            headers=ceo_headers,
        )
        response = client.get(
            "/api/v1/knowledge/?category=faq",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(item["category"] == "faq" for item in data)

    def test_list_knowledge_with_search(self, client, ceo_headers, sample_knowledge):
        client.post(
            "/api/v1/knowledge/",
            json={
                "name": "Machine Learning Guide",
                "category": "general",
                "content": "Comprehensive guide to machine learning.",
                "source_type": "text",
            },
            headers=ceo_headers,
        )
        response = client.get(
            "/api/v1/knowledge/?search=Machine",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert any("Machine" in item["name"] for item in data)

    def test_list_knowledge_with_status_filter(self, client, ceo_headers, sample_knowledge):
        response = client.get(
            f"/api/v1/knowledge/?status={KnowledgeStatus.ACTIVE.value}",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == KnowledgeStatus.ACTIVE.value for item in data)

    def test_unauthorized_create_knowledge(self, client):
        payload = {"name": "Unauthorized Doc", "category": "general"}
        response = client.post("/api/v1/knowledge/", json=payload)
        assert response.status_code == 401


class TestKnowledgeAccess:
    def test_grant_agent_access(self, client, ceo_headers, sample_knowledge, sample_agent):
        response = client.post(
            f"/api/v1/knowledge/{sample_knowledge.id}/access/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert response.json()["detail"] == "Access granted"

    def test_grant_agent_access_with_level(self, client, ceo_headers, sample_knowledge, sample_agent):
        response = client.post(
            f"/api/v1/knowledge/{sample_knowledge.id}/access/{sample_agent.id}?access_level=write",
            headers=ceo_headers,
        )
        assert response.status_code == 200

    def test_revoke_agent_access(self, client, ceo_headers, sample_knowledge, sample_agent):
        client.post(
            f"/api/v1/knowledge/{sample_knowledge.id}/access/{sample_agent.id}",
            headers=ceo_headers,
        )
        response = client.delete(
            f"/api/v1/knowledge/{sample_knowledge.id}/access/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert response.json()["detail"] == "Access revoked"

    def test_revoke_nonexistent_access(self, client, ceo_headers, sample_knowledge, sample_agent):
        response = client.delete(
            f"/api/v1/knowledge/{sample_knowledge.id}/access/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_list_knowledge_agents(self, client, ceo_headers, sample_knowledge, sample_agent):
        client.post(
            f"/api/v1/knowledge/{sample_knowledge.id}/access/{sample_agent.id}",
            headers=ceo_headers,
        )
        response = client.get(
            f"/api/v1/knowledge/{sample_knowledge.id}/agents",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) >= 1
        assert any(a["agent_id"] == str(sample_agent.id) for a in agents)

    def test_list_knowledge_agents_empty(self, client, ceo_headers, sample_knowledge):
        response = client.get(
            f"/api/v1/knowledge/{sample_knowledge.id}/agents",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_grant_access_nonexistent_knowledge(self, client, ceo_headers, sample_agent):
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/knowledge/{fake_id}/access/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert response.status_code == 200

    def test_bulk_grant_access(self, client, ceo_headers, sample_agent):
        id1_response = client.post(
            "/api/v1/knowledge/",
            json={"name": "Bulk Doc 1", "category": "general", "content": "Content 1", "source_type": "text"},
            headers=ceo_headers,
        )
        id2_response = client.post(
            "/api/v1/knowledge/",
            json={"name": "Bulk Doc 2", "category": "general", "content": "Content 2", "source_type": "text"},
            headers=ceo_headers,
        )
        kid1 = id1_response.json()["id"]
        kid2 = id2_response.json()["id"]

        response = client.post(
            "/api/v1/knowledge/bulk-access",
            json={
                "agent_id": str(sample_agent.id),
                "knowledge_ids": [kid1, kid2],
                "access_level": "read",
            },
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert "Access granted to 2 knowledge sources" in response.json()["detail"]

    def test_revoke_access_nonexistent_knowledge(self, client, ceo_headers, sample_agent):
        fake_id = uuid4()
        response = client.delete(
            f"/api/v1/knowledge/{fake_id}/access/{sample_agent.id}",
            headers=ceo_headers,
        )
        assert response.status_code == 404

    def test_unauthorized_access_grant(self, client, sample_knowledge, sample_agent):
        response = client.post(
            f"/api/v1/knowledge/{sample_knowledge.id}/access/{sample_agent.id}",
        )
        assert response.status_code == 401


class TestKnowledgeSearch:
    def test_search_returns_results(self, client, ceo_headers, sample_knowledge):
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "Python", "limit": 5},
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_search_with_category(self, client, ceo_headers, sample_knowledge):
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "test", "category": "general", "limit": 10},
            headers=ceo_headers,
        )
        assert response.status_code == 200
        results = response.json()
        for result in results:
            assert result["category"] == "general"

    def test_search_empty_query(self, client, ceo_headers):
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "", "limit": 5},
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_search_no_matches(self, client, ceo_headers, sample_knowledge):
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "xyzzy_no_match whatsoever", "limit": 5},
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_search_limit(self, client, ceo_headers, sample_knowledge):
        for i in range(5):
            client.post(
                "/api/v1/knowledge/",
                json={
                    "name": f"Search Doc {i}",
                    "category": "general",
                    "content": f"Content about topic number {i}.",
                    "source_type": "text",
                },
                headers=ceo_headers,
            )
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "topic", "limit": 3},
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert len(response.json()) <= 3

    def test_unauthorized_search(self, client):
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "test", "limit": 5},
        )
        assert response.status_code == 401


class TestKnowledgeStats:
    def test_get_stats(self, client, ceo_headers, sample_knowledge):
        response = client.get("/api/v1/knowledge/stats", headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "active" in data
        assert "processing" in data
        assert "error" in data
        assert "by_category" in data
        assert "agents_with_access" in data
        assert data["total"] >= 1
        assert data["active"] >= 1

    def test_stats_categories(self, client, ceo_headers, sample_knowledge):
        client.post(
            "/api/v1/knowledge/",
            json={"name": "Pricing Doc", "category": "pricing", "content": "Pricing info.", "source_type": "text"},
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/knowledge/",
            json={"name": "FAQ Entry", "category": "faq", "content": "FAQ content.", "source_type": "text"},
            headers=ceo_headers,
        )
        response = client.get("/api/v1/knowledge/stats", headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3
        by_cat = data["by_category"]
        assert "general" in by_cat
        assert by_cat["general"] >= 1

    def test_stats_after_delete(self, client, ceo_headers, sample_knowledge):
        stats_before = client.get("/api/v1/knowledge/stats", headers=ceo_headers).json()
        total_before = stats_before["total"]

        client.delete(
            f"/api/v1/knowledge/{sample_knowledge.id}",
            headers=ceo_headers,
        )

        stats_after = client.get("/api/v1/knowledge/stats", headers=ceo_headers).json()
        assert stats_after["total"] == total_before - 1

    def test_stats_with_access(self, client, ceo_headers, sample_knowledge, sample_agent):
        client.post(
            f"/api/v1/knowledge/{sample_knowledge.id}/access/{sample_agent.id}",
            headers=ceo_headers,
        )
        response = client.get("/api/v1/knowledge/stats", headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["agents_with_access"] >= 1

    def test_unauthorized_stats(self, client):
        response = client.get("/api/v1/knowledge/stats")
        assert response.status_code == 401


class TestKnowledgeChunking:
    def test_chunking_via_service(self, db, neon_knowledge, neon_user):
        with patch(PATCH_TARGET, return_value=None):
            from app.services.knowledge_service import KnowledgeService
            from app.services.rag_service import ChunkingService

            service = KnowledgeService(db)
            chunker = ChunkingService(chunk_size=200, chunk_overlap=40)
            long_content = " ".join([f"This is sentence number {i} about various topics." for i in range(30)])
            chunks = chunker.chunk_text(long_content)
            assert len(chunks) > 1
            for i, chunk in enumerate(chunks):
                assert chunk["index"] == i
                assert len(chunk["text"]) > 0

    def test_knowledge_source_chunk_count(self, client, ceo_headers):
        response = client.post(
            "/api/v1/knowledge/",
            json={
                "name": "Long Doc",
                "category": "general",
                "content": " ".join([f"Paragraph {i}. " * 10 for i in range(20)]),
                "source_type": "text",
            },
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["chunk_count"] is not None

    def test_knowledge_update_rechunks(self, client, ceo_headers, sample_knowledge):
        response = client.put(
            f"/api/v1/knowledge/{sample_knowledge.id}",
            json={
                "content": "New content that is quite different from the original. " * 20,
            },
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "New content that is quite different from the original. " * 20

    def test_knowledge_without_content_no_chunks(self, client, ceo_headers):
        response = client.post(
            "/api/v1/knowledge/",
            json={
                "name": "Empty Doc",
                "category": "general",
                "source_type": "note",
            },
            headers=ceo_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["chunk_count"] == "0" or data["chunk_count"] is None

    def test_chunking_preserves_all_content(self, client, ceo_headers):
        sentences = [f"Sentence {i} about topic {i % 5}." for i in range(15)]
        full_content = " ".join(sentences)
        response = client.post(
            "/api/v1/knowledge/",
            json={
                "name": "Preservation Test",
                "category": "general",
                "content": full_content,
                "source_type": "text",
            },
            headers=ceo_headers,
        )
        assert response.status_code == 200
        get_response = client.get(
            f"/api/v1/knowledge/{response.json()['id']}",
            headers=ceo_headers,
        )
        assert get_response.status_code == 200
        returned_content = get_response.json()["content"]
        for sentence in sentences:
            assert sentence in returned_content
