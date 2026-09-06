"""RAG retrieval and context assembly service."""
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeSource, KnowledgeStatus
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.agent_knowledge import AgentKnowledgeAccess
from app.services.embedding_providers import get_embedding_provider
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class ChunkingService:
    """Split text into overlapping chunks for embedding."""

    def __init__(
        self,
        chunk_size: int = settings.RAG_CHUNK_SIZE,
        chunk_overlap: int = settings.RAG_CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        # Split on sentence boundaries, preserving whitespace context
        import re
        sentences = re.split(r'(?<=[.!?\n])\s+', text.strip())
        chunks = []
        current_chunk = ""
        chunk_index = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If single sentence exceeds chunk_size, split it
            if len(sentence) > self.chunk_size:
                if current_chunk:
                    chunks.append(self._make_chunk(current_chunk, chunk_index))
                    chunk_index += 1
                    current_chunk = ""

                # Hard-split long sentences
                for i in range(0, len(sentence), self.chunk_size - self.chunk_overlap):
                    piece = sentence[i:i + self.chunk_size]
                    if piece.strip():
                        chunks.append(self._make_chunk(piece.strip(), chunk_index))
                        chunk_index += 1
                continue

            if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                current_chunk = (current_chunk + " " + sentence).strip()
            else:
                if current_chunk:
                    chunks.append(self._make_chunk(current_chunk, chunk_index))
                    chunk_index += 1
                    # Carry over overlap
                    overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                    current_chunk = (overlap_text + " " + sentence).strip()
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(self._make_chunk(current_chunk, chunk_index))

        return chunks

    def _make_chunk(self, text: str, index: int) -> Dict[str, Any]:
        return {
            "text": text,
            "index": index,
            "token_count": len(text.split()),
        }


class RAGService:
    """Retrieval-Augmented Generation service.

    Handles embedding ingestion, vector search, context assembly,
    and source citations.
    """

    def __init__(self, db: Session):
        self.db = db
        self.vector_store = VectorStore(db)
        self.chunker = ChunkingService()

    async def ingest_knowledge(self, knowledge_id: UUID) -> Dict[str, Any]:
        """Ingest a knowledge source: chunk text, embed, store vectors.

        Returns ingestion stats.
        """
        source = self.db.query(KnowledgeSource).filter(
            KnowledgeSource.id == knowledge_id
        ).first()
        if not source:
            raise ValueError(f"Knowledge source {knowledge_id} not found")

        if not source.content:
            raise ValueError("Knowledge source has no content to ingest")

        # Set processing status
        source.status = KnowledgeStatus.PROCESSING.value
        self.db.commit()

        try:
            # Chunk the content
            chunks = self.chunker.chunk_text(source.content)
            if not chunks:
                source.status = KnowledgeStatus.ERROR.value
                source.chunk_count = "0"
                self.db.commit()
                raise ValueError("No chunks produced from content")

            # Batch embed all chunks
            provider = get_embedding_provider()
            texts = [c["text"] for c in chunks]

            embeddings = await self._batch_embed(texts, provider)

            # Combine chunks with embeddings
            for chunk, embedding in zip(chunks, embeddings):
                chunk["embedding"] = embedding

            # Store in pgvector
            chunk_count = self.vector_store.upsert_chunks(knowledge_id, chunks)

            # Update source metadata
            source.chunk_count = str(chunk_count)
            source.embedding_id = f"emb_{source.id}"
            source.embedding_dimensions = settings.EMBEDDING_DIMENSIONS
            source.status = KnowledgeStatus.ACTIVE.value
            self.db.commit()

            return {
                "knowledge_id": str(knowledge_id),
                "chunk_count": chunk_count,
                "dimensions": settings.EMBEDDING_DIMENSIONS,
                "model": provider.default_model,
                "content_length": len(source.content),
            }

        except Exception as e:
            logger.error(f"Ingestion failed for {knowledge_id}: {e}")
            source.status = KnowledgeStatus.ERROR.value
            self.db.commit()
            raise

    async def _batch_embed(
        self,
        texts: List[str],
        provider,
        batch_size: int = settings.EMBEDDING_BATCH_SIZE,
    ) -> List[List[float]]:
        """Embed texts in batches with retry logic."""
        all_embeddings = []
        max_retries = settings.EMBEDDING_MAX_RETRIES
        retry_delay = settings.EMBEDDING_RETRY_DELAY

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            last_error = None

            for attempt in range(max_retries):
                try:
                    result = await provider.embed_texts(batch)
                    all_embeddings.extend(result.embeddings)
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Embedding batch {i // batch_size} failed "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))

            if last_error is not None:
                raise RuntimeError(
                    f"Embedding failed after {max_retries} retries: {last_error}"
                ) from last_error

        return all_embeddings

    async def search(
        self,
        query: str,
        top_k: int = settings.RAG_DEFAULT_TOP_K,
        knowledge_ids: Optional[List[UUID]] = None,
        threshold: float = settings.RAG_SIMILARITY_THRESHOLD,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for relevant chunks using vector similarity.

        Returns list of chunk results with scores and source metadata.
        """
        provider = get_embedding_provider()
        query_embedding = await provider.embed_query(query)

        results = self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=top_k,
            knowledge_ids=knowledge_ids,
            threshold=threshold,
            metadata_filter=metadata_filter,
        )

        # Enrich with source metadata
        if results:
            knowledge_ids_found = list({r["knowledge_id"] for r in results})
            sources = self.db.query(KnowledgeSource).filter(
                KnowledgeSource.id.in_(knowledge_ids_found)
            ).all()
            source_map = {str(s.id): s for s in sources}

            for result in results:
                source = source_map.get(str(result["knowledge_id"]))
                if source:
                    result["source_name"] = source.name
                    result["source_category"] = source.category
                    result["source_type"] = source.source_type
                else:
                    result["source_name"] = "Unknown"
                    result["source_category"] = "general"
                    result["source_type"] = "unknown"

        return results

    async def search_with_permissions(
        self,
        query: str,
        agent_id: UUID,
        top_k: int = settings.RAG_DEFAULT_TOP_K,
        threshold: float = settings.RAG_SIMILARITY_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        """Search filtered to knowledge accessible by a specific agent."""
        # Get knowledge IDs accessible by this agent
        accessible_ids = [
            ak.knowledge_id for ak in
            self.db.query(AgentKnowledgeAccess.knowledge_id).filter(
                AgentKnowledgeAccess.agent_id == agent_id
            ).all()
        ]

        if not accessible_ids:
            return []

        return await self.search(
            query=query,
            top_k=top_k,
            knowledge_ids=accessible_ids,
            threshold=threshold,
        )

    async def assemble_context(
        self,
        query: str,
        agent_id: Optional[UUID] = None,
        top_k: int = settings.RAG_DEFAULT_TOP_K,
        max_context_length: int = 4000,
    ) -> Dict[str, Any]:
        """Retrieve relevant chunks and assemble RAG context with citations.

        Returns dict with:
        - context: formatted context string
        - sources: list of source citations
        - chunks: raw chunk results
        """
        if agent_id:
            chunks = await self.search_with_permissions(query, agent_id, top_k=top_k)
        else:
            chunks = await self.search(query, top_k=top_k)

        if not chunks:
            return {
                "context": "No relevant knowledge found.",
                "sources": [],
                "chunks": [],
            }

        # Build context with citations
        context_parts = []
        sources = []
        current_length = 0
        seen_sources = set()

        for i, chunk in enumerate(chunks):
            source_key = str(chunk["knowledge_id"])
            chunk_text = chunk["content"]

            # Truncate if adding this chunk would exceed max context
            if current_length + len(chunk_text) > max_context_length:
                remaining = max_context_length - current_length
                if remaining > 100:
                    chunk_text = chunk_text[:remaining] + "..."
                else:
                    break

            citation_num = i + 1
            context_parts.append(
                f"[{citation_num}] ({chunk.get('source_name', 'Unknown')}) "
                f"{chunk_text}"
            )
            current_length += len(chunk_text)

            # Build citation
            if source_key not in seen_sources:
                sources.append({
                    "citation_number": citation_num,
                    "knowledge_id": source_key,
                    "source_name": chunk.get("source_name", "Unknown"),
                    "category": chunk.get("source_category", "general"),
                    "score": chunk.get("score", 0.0),
                    "chunk_index": chunk.get("chunk_index", 0),
                })
                seen_sources.add(source_key)

        return {
            "context": "\n\n".join(context_parts),
            "sources": sources,
            "chunks": [
                {
                    "content": c["content"],
                    "score": c.get("score", 0.0),
                    "source_name": c.get("source_name"),
                    "chunk_index": c.get("chunk_index"),
                }
                for c in chunks
            ],
        }

    async def reprocess_knowledge(self, knowledge_id: UUID) -> Dict[str, Any]:
        """Re-embed and reprocess a knowledge source from scratch."""
        # Delete old chunks
        self.vector_store.delete_chunks(knowledge_id)

        # Re-ingest
        return await self.ingest_knowledge(knowledge_id)

    async def reprocess_all(self) -> Dict[str, Any]:
        """Re-embed all active knowledge sources."""
        sources = self.db.query(KnowledgeSource).filter(
            KnowledgeSource.status == KnowledgeStatus.ACTIVE.value
        ).all()

        results = {"success": 0, "failed": 0, "errors": []}
        for source in sources:
            if source.content:
                try:
                    await self.reprocess_knowledge(source.id)
                    results["success"] += 1
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "knowledge_id": str(source.id),
                        "error": str(e),
                    })

        return results
