"""Tests for pgvector-backed vector store."""
import pytest
from uuid import uuid4

from app.core.config import settings
from app.models.knowledge import KnowledgeSource, KnowledgeStatus
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.vector_store import VectorStore


DIM = settings.EMBEDDING_DIMENSIONS  # 1536


class TestVectorStore:
    def test_upsert_chunks(self, db, sample_knowledge):
        store = VectorStore(db)
        chunks = [
            {"index": 0, "text": "First chunk", "embedding": [0.1] * DIM},
            {"index": 1, "text": "Second chunk", "embedding": [0.2] * DIM},
        ]

        count = store.upsert_chunks(sample_knowledge.id, chunks)
        assert count == 2

        db_chunks = store.get_all_chunks(sample_knowledge.id)
        assert len(db_chunks) == 2
        assert db_chunks[0].content == "First chunk"
        assert db_chunks[1].content == "Second chunk"

    def test_upsert_replaces_existing(self, db, sample_knowledge):
        store = VectorStore(db)

        store.upsert_chunks(sample_knowledge.id, [
            {"index": 0, "text": "Old chunk", "embedding": [0.1] * DIM},
        ])
        db.flush()

        store.upsert_chunks(sample_knowledge.id, [
            {"index": 0, "text": "New chunk", "embedding": [0.2] * DIM},
            {"index": 1, "text": "Another chunk", "embedding": [0.3] * DIM},
        ])
        db.flush()

        db_chunks = store.get_all_chunks(sample_knowledge.id)
        assert len(db_chunks) == 2
        assert db_chunks[0].content == "New chunk"

    def test_delete_chunks(self, db, sample_knowledge):
        store = VectorStore(db)
        store.upsert_chunks(sample_knowledge.id, [
            {"index": 0, "text": "To delete", "embedding": [0.1] * DIM},
        ])
        db.flush()

        count = store.delete_chunks(sample_knowledge.id)
        assert count == 1
        assert store.get_chunk_count(sample_knowledge.id) == 0

    def test_get_chunk_count(self, db, sample_knowledge):
        store = VectorStore(db)
        assert store.get_chunk_count(sample_knowledge.id) == 0

        store.upsert_chunks(sample_knowledge.id, [
            {"index": 0, "text": "A", "embedding": [0.1] * DIM},
            {"index": 1, "text": "B", "embedding": [0.2] * DIM},
            {"index": 2, "text": "C", "embedding": [0.3] * DIM},
        ])
        db.flush()

        assert store.get_chunk_count(sample_knowledge.id) == 3

    def test_similarity_search_basic(self, db, sample_knowledge):
        store = VectorStore(db)

        # Create vectors with varying similarity to the query
        vec_a = [1.0] + [0.0] * (DIM - 1)
        # vec_b: partially similar (shares some dimension)
        vec_b = [0.7] + [0.3] + [0.0] * (DIM - 2)

        chunks = [
            {"index": 0, "text": "About Python", "embedding": vec_a},
            {"index": 1, "text": "About JavaScript", "embedding": vec_b},
        ]
        store.upsert_chunks(sample_knowledge.id, chunks)
        db.flush()

        results = store.similarity_search(vec_a, top_k=5, threshold=0.0)

        # Should return at least the exact match
        assert len(results) >= 1
        # Most similar should be vec_a itself (score ~1.0)
        assert results[0]["content"] == "About Python"
        assert results[0]["score"] > results[1]["score"] if len(results) > 1 else True

    def test_similarity_search_with_knowledge_ids(self, db, sample_user):
        store = VectorStore(db)

        ks1 = KnowledgeSource(
            id=uuid4(), name="Source 1", category="general",
            content="Content 1", source_type="text",
            status=KnowledgeStatus.ACTIVE.value,
            created_by=sample_user.id,
        )
        ks2 = KnowledgeSource(
            id=uuid4(), name="Source 2", category="general",
            content="Content 2", source_type="text",
            status=KnowledgeStatus.ACTIVE.value,
            created_by=sample_user.id,
        )
        db.add_all([ks1, ks2])
        db.flush()

        store.upsert_chunks(ks1.id, [
            {"index": 0, "text": "Chunk from source 1", "embedding": [1.0] + [0.0] * (DIM - 1)},
        ])
        store.upsert_chunks(ks2.id, [
            {"index": 0, "text": "Chunk from source 2", "embedding": [0.0, 1.0] + [0.0] * (DIM - 2)},
        ])
        db.flush()

        results = store.similarity_search(
            query_embedding=[1.0] + [0.0] * (DIM - 1),
            top_k=10,
            knowledge_ids=[ks1.id],
        )

        assert len(results) == 1
        assert results[0]["content"] == "Chunk from source 1"

    def test_similarity_search_threshold(self, db, sample_knowledge):
        store = VectorStore(db)

        store.upsert_chunks(sample_knowledge.id, [
            {"index": 0, "text": "Similar", "embedding": [1.0] + [0.0] * (DIM - 1)},
            {"index": 1, "text": "Not similar", "embedding": [0.0, 1.0] + [0.0] * (DIM - 2)},
        ])
        db.flush()

        results = store.similarity_search(
            query_embedding=[1.0] + [0.0] * (DIM - 1),
            top_k=10,
            threshold=0.9,
        )

        assert len(results) <= 1
        if results:
            assert results[0]["content"] == "Similar"

    def test_similarity_search_empty(self, db):
        store = VectorStore(db)
        results = store.similarity_search(
            query_embedding=[1.0] + [0.0] * (DIM - 1),
            top_k=5,
        )
        assert results == []
