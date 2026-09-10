import asyncio
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.knowledge import KnowledgeSource, KnowledgeStatus
from app.models.agent_knowledge import AgentKnowledgeAccess
from app.models.agent import AIAgent
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate, BulkAccessRequest
from app.services.rag_service import RAGService
from app.utils.async_utils import run_async

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db
        self.rag = RAGService(db)

    def get_sources(
        self,
        category: Optional[str] = None,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        user_id: Optional[UUID] = None,
    ) -> List[KnowledgeSource]:
        query = self.db.query(KnowledgeSource)
        if user_id is not None:
            query = query.filter(KnowledgeSource.created_by == user_id)
        if category:
            query = query.filter(KnowledgeSource.category == category)
        if source_type:
            query = query.filter(KnowledgeSource.source_type == source_type)
        if status:
            query = query.filter(KnowledgeSource.status == status)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                KnowledgeSource.name.ilike(search_term)
                | KnowledgeSource.description.ilike(search_term)
            )
        return query.order_by(KnowledgeSource.created_at.desc()).all()

    def get_source(self, source_id: UUID, user_id: Optional[UUID] = None) -> Optional[KnowledgeSource]:
        query = self.db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id)
        if user_id is not None:
            query = query.filter(KnowledgeSource.created_by == user_id)
        return query.first()

    def create_source(self, data: KnowledgeCreate, created_by: Optional[UUID] = None) -> KnowledgeSource:
        source = KnowledgeSource(**data.model_dump(), created_by=created_by)
        self.db.add(source)
        self.db.flush()

        if source.content:
            try:
                result = run_async(self.rag.ingest_knowledge(source.id))
                source.chunk_count = str(result["chunk_count"])
                source.embedding_id = f"emb_{source.id}"
            except Exception as e:
                logger.error(f"Failed to ingest knowledge {source.id}: {e}")
                source.status = KnowledgeStatus.ERROR.value

        self.db.commit()
        self.db.refresh(source)
        return source

    def update_source(self, source_id: UUID, data: KnowledgeUpdate, user_id: Optional[UUID] = None) -> Optional[KnowledgeSource]:
        source = self.get_source(source_id, user_id=user_id)
        if source:
            update_data = data.model_dump(exclude_unset=True)
            content_changed = "content" in update_data
            for key, value in update_data.items():
                setattr(source, key, value)

            if content_changed and source.content:
                try:
                    self.rag.vector_store.delete_chunks(source.id)
                    result = run_async(self.rag.ingest_knowledge(source.id))
                    source.chunk_count = str(result["chunk_count"])
                    source.embedding_id = f"emb_{source.id}"
                    source.status = KnowledgeStatus.ACTIVE.value
                except Exception as e:
                    logger.error(f"Failed to re-ingest knowledge {source.id}: {e}")
                    source.status = KnowledgeStatus.ERROR.value

            self.db.commit()
            self.db.refresh(source)
        return source

    def delete_source(self, source_id: UUID, user_id: Optional[UUID] = None) -> bool:
        source = self.get_source(source_id, user_id=user_id)
        if source:
            self.rag.vector_store.delete_chunks(source_id)
            self.db.query(AgentKnowledgeAccess).filter(
                AgentKnowledgeAccess.knowledge_id == source_id
            ).delete()
            self.db.delete(source)
            self.db.commit()
            return True
        return False

    def grant_access(self, agent_id: UUID, knowledge_id: UUID, access_level: str = "read", granted_by: str = "system") -> AgentKnowledgeAccess:
        existing = self.db.query(AgentKnowledgeAccess).filter(
            AgentKnowledgeAccess.agent_id == agent_id,
            AgentKnowledgeAccess.knowledge_id == knowledge_id
        ).first()

        if existing:
            existing.access_level = access_level
            existing.granted_by = granted_by
            self.db.commit()
            self.db.refresh(existing)
            return existing

        access = AgentKnowledgeAccess(
            agent_id=agent_id,
            knowledge_id=knowledge_id,
            access_level=access_level,
            granted_by=granted_by,
        )
        self.db.add(access)
        self.db.commit()
        self.db.refresh(access)
        return access

    def revoke_access(self, agent_id: UUID, knowledge_id: UUID) -> bool:
        access = self.db.query(AgentKnowledgeAccess).filter(
            AgentKnowledgeAccess.agent_id == agent_id,
            AgentKnowledgeAccess.knowledge_id == knowledge_id
        ).first()

        if access:
            self.db.delete(access)
            self.db.commit()
            return True
        return False

    def bulk_grant_access(self, agent_id: UUID, knowledge_ids: List[UUID], access_level: str = "read", granted_by: str = "system") -> int:
        count = 0
        for kid in knowledge_ids:
            self.grant_access(agent_id, kid, access_level, granted_by)
            count += 1
        return count

    def get_agent_accessible_knowledge(self, agent_id: UUID) -> List[KnowledgeSource]:
        access_records = self.db.query(AgentKnowledgeAccess).filter(
            AgentKnowledgeAccess.agent_id == agent_id
        ).all()

        knowledge_ids = [a.knowledge_id for a in access_records]
        if not knowledge_ids:
            return []
        return self.db.query(KnowledgeSource).filter(
            KnowledgeSource.id.in_(knowledge_ids),
            KnowledgeSource.status == KnowledgeStatus.ACTIVE.value,
        ).all()

    def get_knowledge_agents(self, knowledge_id: UUID) -> List[Dict[str, Any]]:
        access_records = self.db.query(AgentKnowledgeAccess).filter(
            AgentKnowledgeAccess.knowledge_id == knowledge_id
        ).all()

        agent_ids = [a.agent_id for a in access_records]
        if not agent_ids:
            return []

        agents = self.db.query(AIAgent).filter(AIAgent.id.in_(agent_ids)).all()
        agent_map = {a.id: a for a in agents}

        result = []
        for access in access_records:
            agent = agent_map.get(access.agent_id)
            if agent:
                result.append({
                    "id": str(access.id),
                    "knowledge_id": str(access.knowledge_id),
                    "agent_id": str(agent.id),
                    "agent_name": agent.name,
                    "access_level": access.access_level,
                    "granted_by": access.granted_by,
                    "created_at": access.created_at,
                })
        return result

    def search_knowledge(self, query: str, category: Optional[str] = None, limit: int = 10, user_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """Search knowledge using vector similarity + keyword matching."""
        # Vector search via RAG
        try:
            vector_results = run_async(
                self.rag.search(query, top_k=limit)
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            vector_results = []

        # Build results from vector search
        results = []
        for vr in vector_results:
            entry = {
                "id": str(vr["knowledge_id"]),
                "name": vr.get("source_name", "Unknown"),
                "category": vr.get("source_category", "general"),
                "source_type": vr.get("source_type", "unknown"),
                "snippet": vr["content"][:300],
                "score": vr.get("score", 0.0),
                "vector_score": vr.get("score", 0.0),
                "chunk_index": vr.get("chunk_index", 0),
            }

            # Apply category filter
            if category and entry["category"] != category:
                continue

            # Apply user filter if provided
            if user_id is not None:
                source = self.get_source(UUID(entry["id"]))
                if not source or source.created_by != user_id:
                    continue

            results.append(entry)

        # If vector search returned few results, supplement with keyword search
        if len(results) < limit:
            keyword_results = self._keyword_search(query, category, limit - len(results), user_id=user_id)
            existing_ids = {r["id"] for r in results}
            for kr in keyword_results:
                if kr["id"] not in existing_ids:
                    results.append(kr)

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def _keyword_search(self, query: str, category: Optional[str] = None, limit: int = 5, user_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """Fallback keyword search for when vector search returns few results."""
        query_lower = query.lower()
        query_words = query_lower.split()

        sources = self.get_sources(category=category, status="active", user_id=user_id)
        results = []

        for source in sources:
            score = 0
            content_lower = (source.content or "").lower()
            name_lower = source.name.lower()

            if query_lower in name_lower:
                score += 10
            for word in query_words:
                if word in content_lower:
                    score += content_lower.count(word)
                if word in name_lower:
                    score += 5

            if score > 0:
                snippet = self._extract_snippet(source.content or "", query_lower)
                results.append({
                    "id": str(source.id),
                    "name": source.name,
                    "category": source.category,
                    "source_type": source.source_type,
                    "snippet": snippet,
                    "score": float(score),
                    "vector_score": 0.0,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def _extract_snippet(self, content: str, query: str, context_length: int = 200) -> str:
        if not content:
            return ""
        content_lower = content.lower()
        idx = content_lower.find(query)
        if idx == -1:
            return content[:context_length] + "..." if len(content) > context_length else content
        start = max(0, idx - context_length // 2)
        end = min(len(content), idx + len(query) + context_length // 2)
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        return snippet

    def get_knowledge_stats(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        query = self.db.query(KnowledgeSource)
        if user_id is not None:
            query = query.filter(KnowledgeSource.created_by == user_id)

        total = query.count()
        active = query.filter(KnowledgeSource.status == KnowledgeStatus.ACTIVE.value).count()
        processing = query.filter(KnowledgeSource.status == KnowledgeStatus.PROCESSING.value).count()
        error = query.filter(KnowledgeSource.status == KnowledgeStatus.ERROR.value).count()

        categories = {}
        category_counts = query.with_entities(KnowledgeSource.category).distinct().all()
        for cat in category_counts:
            count = query.filter(KnowledgeSource.category == cat[0]).count()
            categories[cat[0]] = count

        total_agents_with_access = self.db.query(AgentKnowledgeAccess.agent_id).distinct().count()

        return {
            "total": total,
            "active": active,
            "processing": processing,
            "error": error,
            "by_category": categories,
            "agents_with_access": total_agents_with_access,
        }

    def get_agent_knowledge_context(self, agent_id: UUID, query: str) -> Dict[str, Any]:
        """Get RAG context for an agent with source citations."""
        try:
            result = run_async(
                self.rag.assemble_context(query, agent_id=agent_id)
            )
            return result
        except Exception as e:
            logger.error(f"RAG context assembly failed: {e}")
            # Fallback to basic keyword search
            return self._fallback_context(agent_id, query)

    def _fallback_context(self, agent_id: UUID, query: str) -> Dict[str, Any]:
        """Fallback context when vector search fails."""
        accessible = self.get_agent_accessible_knowledge(agent_id)
        if not accessible:
            return {"context": "No knowledge base available.", "sources": [], "chunks": []}

        query_lower = query.lower()
        relevant = []
        for source in accessible:
            if source.content and query_lower in source.content.lower():
                relevant.append(source)
        if not relevant:
            relevant = accessible[:3]

        context_parts = []
        sources = []
        for i, source in enumerate(relevant[:5]):
            context_parts.append(f"[{i+1}] ({source.name}) {source.content[:500]}")
            sources.append({
                "citation_number": i + 1,
                "knowledge_id": str(source.id),
                "source_name": source.name,
                "category": source.category,
                "score": 0.0,
            })

        return {
            "context": "\n\n".join(context_parts),
            "sources": sources,
            "chunks": [],
        }

    def reprocess_embeddings(self, source_id: UUID, user_id: Optional[UUID] = None) -> bool:
        source = self.get_source(source_id, user_id=user_id)
        if not source or not source.content:
            return False
        try:
            run_async(self.rag.reprocess_knowledge(source_id))
            self.db.refresh(source)
            return True
        except Exception as e:
            logger.error(f"Reprocessing failed for {source_id}: {e}")
            source.status = KnowledgeStatus.ERROR.value
            self.db.commit()
            return False
