"""pgvector-backed vector store for knowledge chunks."""
import logging
import re
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk

logger = logging.getLogger(__name__)

MAX_TOP_K = 100


def _validate_embedding(embedding: List[float]) -> str:
    """Safely convert embedding to a pgvector-compatible string.

    Validates each value is a finite float to prevent SQL injection.
    """
    if not embedding:
        raise ValueError("Embedding cannot be empty")
    parts = []
    for v in embedding:
        f = float(v)
        if not (-1e10 <= f <= 1e10):
            raise ValueError(f"Embedding value out of range: {f}")
        parts.append(f"{f:.8f}")
    return "[" + ",".join(parts) + "]"


def _validate_top_k(top_k: int) -> int:
    """Clamp top_k to a safe range."""
    return max(1, min(top_k, MAX_TOP_K))


class VectorStore:
    """Vector similarity search backed by PostgreSQL pgvector."""

    def __init__(self, db: Session):
        self.db = db

    def upsert_chunks(
        self,
        knowledge_id: UUID,
        chunks: List[Dict[str, Any]],
    ) -> int:
        """Insert or replace all chunks for a knowledge source.

        Each chunk dict must have: text, index, embedding, and optional metadata.
        Returns the number of chunks upserted.
        """
        self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.knowledge_id == knowledge_id
        ).delete(synchronize_session="fetch")

        logger.debug("Upserting %d chunks for knowledge_id=%s", len(chunks), knowledge_id)
        count = 0
        for chunk_data in chunks:
            chunk = KnowledgeChunk(
                knowledge_id=knowledge_id,
                chunk_index=chunk_data["index"],
                content=chunk_data["text"],
                embedding=chunk_data["embedding"],
                token_count=chunk_data.get("token_count"),
                metadata_json=chunk_data.get("metadata"),
            )
            self.db.add(chunk)
            count += 1

        self.db.flush()
        logger.debug("Upserted %d chunks for knowledge_id=%s", count, knowledge_id)
        return count

    def delete_chunks(self, knowledge_id: UUID) -> int:
        """Delete all chunks for a knowledge source."""
        count = self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.knowledge_id == knowledge_id
        ).delete(synchronize_session="fetch")
        self.db.flush()
        return count

    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        knowledge_ids: Optional[List[UUID]] = None,
        threshold: float = 0.0,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Find the most similar chunks using cosine distance.

        Parameters
        ----------
        query_embedding:
            The embedding vector of the query.
        top_k:
            Number of results to return (max 100).
        knowledge_ids:
            If provided, restrict search to these knowledge sources.
        threshold:
            Minimum similarity score (0-1) to include.
        metadata_filter:
            Optional JSON metadata filter.

        Returns
        -------
        List of dicts with keys: knowledge_id, chunk_id, chunk_index,
        content, score, metadata_json.
        """
        logger.debug("Similarity search: top_k=%d threshold=%f ids=%s", top_k, threshold, knowledge_ids)
        top_k = _validate_top_k(top_k)
        embedding_str = _validate_embedding(query_embedding)

        if knowledge_ids:
            kid_list = ",".join(f"'{kid}'" for kid in knowledge_ids)
            query = text(f"""
                SELECT
                    kc.knowledge_id,
                    kc.id AS chunk_id,
                    kc.chunk_index,
                    kc.content,
                    kc.metadata_json,
                    1 - (kc.embedding <=> CAST(:embedding AS vector)) AS score
                FROM knowledge_chunks kc
                WHERE kc.embedding IS NOT NULL
                AND kc.knowledge_id IN ({kid_list})
                AND (:threshold IS NULL OR 1 - (kc.embedding <=> CAST(:embedding AS vector)) >= :threshold)
                ORDER BY kc.embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
            """)
        else:
            query = text("""
                SELECT
                    kc.knowledge_id,
                    kc.id AS chunk_id,
                    kc.chunk_index,
                    kc.content,
                    kc.metadata_json,
                    1 - (kc.embedding <=> CAST(:embedding AS vector)) AS score
                FROM knowledge_chunks kc
                WHERE kc.embedding IS NOT NULL
                AND (:threshold IS NULL OR 1 - (kc.embedding <=> CAST(:embedding AS vector)) >= :threshold)
                ORDER BY kc.embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
            """)

        params = {
            "embedding": embedding_str,
            "top_k": top_k,
            "threshold": float(threshold) if threshold > 0 else None,
        }

        try:
            result = self.db.execute(query, params)
        except Exception:
            logger.error("Vector similarity search failed", exc_info=True)
            return []
        rows = result.fetchall()

        logger.debug("Similarity search returned %d results", len(rows))
        results = []
        for row in rows:
            entry = {
                "knowledge_id": row[0],
                "chunk_id": row[1],
                "chunk_index": row[2],
                "content": row[3],
                "metadata_json": row[4],
                "score": float(row[5]) if row[5] is not None else 0.0,
            }
            results.append(entry)

        return results

    def get_chunk_count(self, knowledge_id: UUID) -> int:
        return self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.knowledge_id == knowledge_id
        ).count()

    def get_all_chunks(self, knowledge_id: UUID) -> List[KnowledgeChunk]:
        return self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.knowledge_id == knowledge_id
        ).order_by(KnowledgeChunk.chunk_index).all()
