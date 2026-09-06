"""Tests for KnowledgeService integration with RAG pipeline."""
import pytest
from unittest.mock import patch
from uuid import uuid4

from app.models.knowledge import KnowledgeSource, KnowledgeStatus
from app.models.agent_knowledge import AgentKnowledgeAccess
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, BulkAccessRequest
from app.services.knowledge_service import KnowledgeService


PATCH_TARGET = "app.services.rag_service.get_embedding_provider"


class TestKnowledgeServiceCRUD:
    @pytest.mark.asyncio
    async def test_create_source_with_content(self, db, sample_user, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            service = KnowledgeService(db)
            data = KnowledgeCreate(
                name="Test Doc",
                content="This is test content about AI and machine learning.",
                category="general",
                source_type="text",
            )
            source = service.create_source(data, created_by=sample_user.id)

        assert source.name == "Test Doc"
        assert source.status == KnowledgeStatus.ACTIVE.value
        assert int(source.chunk_count) >= 1

    def test_create_source_without_content(self, db, sample_user):
        service = KnowledgeService(db)
        data = KnowledgeCreate(
            name="Empty Doc",
            category="general",
            source_type="note",
        )
        source = service.create_source(data, created_by=sample_user.id)
        assert source.name == "Empty Doc"
        assert source.chunk_count == "0"

    @pytest.mark.asyncio
    async def test_update_source_content(self, db, sample_knowledge, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            service = KnowledgeService(db)
            data = KnowledgeUpdate(content="Updated content about neural networks.")
            updated = service.update_source(sample_knowledge.id, data)

        assert updated is not None
        assert updated.content == "Updated content about neural networks."
        assert int(updated.chunk_count) >= 1

    def test_update_source_metadata(self, db, sample_knowledge):
        service = KnowledgeService(db)
        data = KnowledgeUpdate(name="Updated Name")
        updated = service.update_source(sample_knowledge.id, data)
        assert updated.name == "Updated Name"

    def test_delete_source(self, db, sample_knowledge):
        service = KnowledgeService(db)
        result = service.delete_source(sample_knowledge.id)
        assert result is True
        assert service.get_source(sample_knowledge.id) is None

    def test_delete_nonexistent(self, db):
        service = KnowledgeService(db)
        result = service.delete_source(uuid4())
        assert result is False

    def test_get_sources_filter(self, db, sample_knowledge, sample_user):
        service = KnowledgeService(db)
        data = KnowledgeCreate(name="FAQ", category="faq", content="FAQ content")
        service.create_source(data, created_by=sample_user.id)

        all_sources = service.get_sources()
        assert len(all_sources) == 2

        faq_sources = service.get_sources(category="faq")
        assert len(faq_sources) == 1
        assert faq_sources[0].name == "FAQ"

    def test_get_source(self, db, sample_knowledge):
        service = KnowledgeService(db)
        source = service.get_source(sample_knowledge.id)
        assert source is not None
        assert source.name == "Test Knowledge"

    @pytest.mark.asyncio
    async def test_search_knowledge(self, db, sample_knowledge, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            service = KnowledgeService(db)
            results = service.search_knowledge("Python", limit=5)
        assert isinstance(results, list)


class TestKnowledgeAccessControl:
    def test_grant_access(self, db, sample_agent, sample_knowledge):
        service = KnowledgeService(db)
        access = service.grant_access(sample_agent.id, sample_knowledge.id, "read", "test")
        assert access.agent_id == sample_agent.id
        assert access.knowledge_id == sample_knowledge.id
        assert access.access_level == "read"

    def test_grant_access_idempotent(self, db, sample_agent, sample_knowledge):
        service = KnowledgeService(db)
        service.grant_access(sample_agent.id, sample_knowledge.id, "read")
        updated = service.grant_access(sample_agent.id, sample_knowledge.id, "write")
        assert updated.access_level == "write"

    def test_revoke_access(self, db, sample_agent, sample_knowledge):
        service = KnowledgeService(db)
        service.grant_access(sample_agent.id, sample_knowledge.id)
        result = service.revoke_access(sample_agent.id, sample_knowledge.id)
        assert result is True
        accessible = service.get_agent_accessible_knowledge(sample_agent.id)
        assert len(accessible) == 0

    def test_revoke_nonexistent(self, db, sample_agent, sample_knowledge):
        service = KnowledgeService(db)
        result = service.revoke_access(sample_agent.id, sample_knowledge.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_bulk_grant_access(self, db, sample_agent, sample_user, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            service = KnowledgeService(db)
            ids = []
            for i in range(3):
                data = KnowledgeCreate(name=f"Doc {i}", content=f"Content {i}")
                source = service.create_source(data, created_by=sample_user.id)
                ids.append(source.id)

        count = service.bulk_grant_access(sample_agent.id, ids)
        assert count == 3

        accessible = service.get_agent_accessible_knowledge(sample_agent.id)
        assert len(accessible) == 3

    def test_get_agent_accessible_knowledge(self, db, sample_agent, sample_knowledge):
        service = KnowledgeService(db)
        service.grant_access(sample_agent.id, sample_knowledge.id)

        accessible = service.get_agent_accessible_knowledge(sample_agent.id)
        assert len(accessible) == 1
        assert accessible[0].id == sample_knowledge.id

    def test_get_knowledge_agents(self, db, sample_agent, sample_knowledge):
        service = KnowledgeService(db)
        service.grant_access(sample_agent.id, sample_knowledge.id)

        agents = service.get_knowledge_agents(sample_knowledge.id)
        assert len(agents) == 1
        assert agents[0]["agent_id"] == str(sample_agent.id)
        assert agents[0]["agent_name"] == "Test Agent"


class TestKnowledgeStats:
    def test_get_stats(self, db, sample_knowledge, sample_user):
        service = KnowledgeService(db)
        stats = service.get_knowledge_stats()
        assert stats["total"] >= 1
        assert stats["active"] >= 1
        assert "by_category" in stats


class TestKnowledgeContext:
    @pytest.mark.asyncio
    async def test_get_agent_knowledge_context(self, db, sample_knowledge, sample_agent, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            service = KnowledgeService(db)
            service.grant_access(sample_agent.id, sample_knowledge.id)
            result = service.get_agent_knowledge_context(sample_agent.id, "Python")

        assert "context" in result
        assert "sources" in result
        assert isinstance(result["sources"], list)
