"""Tests for RAG service: ingestion, retrieval, context assembly."""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.core.config import settings
from app.models.knowledge import KnowledgeSource, KnowledgeStatus
from app.models.agent_knowledge import AgentKnowledgeAccess
from app.services.rag_service import RAGService, ChunkingService
from app.services.embedding_providers.base import EmbeddingResult


PATCH_TARGET = "app.services.rag_service.get_embedding_provider"


class TestRAGIngestion:
    @pytest.mark.asyncio
    async def test_ingest_knowledge(self, db, sample_knowledge, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            result = await rag.ingest_knowledge(sample_knowledge.id)

        assert result["chunk_count"] >= 1
        assert result["dimensions"] == settings.EMBEDDING_DIMENSIONS
        assert result["model"] == "mock-embed-v1"

        db.refresh(sample_knowledge)
        assert sample_knowledge.status == KnowledgeStatus.ACTIVE.value
        assert int(sample_knowledge.chunk_count) >= 1

    @pytest.mark.asyncio
    async def test_ingest_empty_content(self, db, sample_user):
        source = KnowledgeSource(
            id=uuid4(), name="Empty", category="general",
            content="", source_type="text",
            status=KnowledgeStatus.ACTIVE.value,
            created_by=sample_user.id,
        )
        db.add(source)
        db.flush()

        with patch(PATCH_TARGET):
            rag = RAGService(db)
            with pytest.raises(ValueError, match="no content"):
                await rag.ingest_knowledge(source.id)

    @pytest.mark.asyncio
    async def test_ingest_missing_source(self, db):
        rag = RAGService(db)
        with pytest.raises(ValueError, match="not found"):
            await rag.ingest_knowledge(uuid4())

    @pytest.mark.asyncio
    async def test_ingest_sets_error_on_failure(self, db, sample_knowledge):
        failing_provider = AsyncMock()
        failing_provider.embed_texts = AsyncMock(side_effect=Exception("API Error"))
        failing_provider.default_model = "fail-model"
        failing_provider.default_dimensions = 128

        with patch(PATCH_TARGET, return_value=failing_provider):
            rag = RAGService(db)
            with pytest.raises(Exception, match="API Error"):
                await rag.ingest_knowledge(sample_knowledge.id)

        db.refresh(sample_knowledge)
        assert sample_knowledge.status == KnowledgeStatus.ERROR.value


class TestRAGSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, db, sample_knowledge, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            await rag.ingest_knowledge(sample_knowledge.id)
            results = await rag.search("Python programming", top_k=5)

        assert len(results) > 0
        assert "content" in results[0]
        assert "score" in results[0]
        assert "source_name" in results[0]

    @pytest.mark.asyncio
    async def test_search_empty_knowledge(self, db, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            results = await rag.search("anything", top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_threshold(self, db, sample_knowledge, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            await rag.ingest_knowledge(sample_knowledge.id)
            results = await rag.search("Python", top_k=5, threshold=0.99)

        assert isinstance(results, list)


class TestRAGPermissions:
    @pytest.mark.asyncio
    async def test_search_with_permissions(self, db, sample_knowledge, sample_agent, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            await rag.ingest_knowledge(sample_knowledge.id)

            access = AgentKnowledgeAccess(
                agent_id=sample_agent.id,
                knowledge_id=sample_knowledge.id,
                access_level="read",
            )
            db.add(access)
            db.flush()

            results = await rag.search_with_permissions("Python", sample_agent.id, top_k=5)

        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_with_no_permissions(self, db, sample_knowledge, sample_agent, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            await rag.ingest_knowledge(sample_knowledge.id)

            results = await rag.search_with_permissions("Python", sample_agent.id, top_k=5)

        assert results == []


class TestRAGContextAssembly:
    @pytest.mark.asyncio
    async def test_assemble_context(self, db, sample_knowledge, sample_agent, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            await rag.ingest_knowledge(sample_knowledge.id)

            access = AgentKnowledgeAccess(
                agent_id=sample_agent.id,
                knowledge_id=sample_knowledge.id,
                access_level="read",
            )
            db.add(access)
            db.flush()

            result = await rag.assemble_context("Python programming", agent_id=sample_agent.id)

        assert "context" in result
        assert "sources" in result
        assert "chunks" in result
        assert len(result["context"]) > 0
        assert isinstance(result["sources"], list)

    @pytest.mark.asyncio
    async def test_assemble_context_no_access(self, db, sample_knowledge, sample_agent, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            await rag.ingest_knowledge(sample_knowledge.id)

            result = await rag.assemble_context("Python", agent_id=sample_agent.id)

        assert result["context"] == "No relevant knowledge found."
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_assemble_context_no_agent(self, db, sample_knowledge, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            await rag.ingest_knowledge(sample_knowledge.id)

            result = await rag.assemble_context("Python", agent_id=None)

        assert "context" in result


class TestRAGReprocessing:
    @pytest.mark.asyncio
    async def test_reprocess_knowledge(self, db, sample_knowledge, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            await rag.ingest_knowledge(sample_knowledge.id)

            result = await rag.reprocess_knowledge(sample_knowledge.id)

        assert result["chunk_count"] >= 1

    @pytest.mark.asyncio
    async def test_reprocess_all(self, db, sample_knowledge, mock_embedding_provider):
        with patch(PATCH_TARGET, return_value=mock_embedding_provider):
            rag = RAGService(db)
            await rag.ingest_knowledge(sample_knowledge.id)

            result = await rag.reprocess_all()

        assert result["success"] == 1
        assert result["failed"] == 0
