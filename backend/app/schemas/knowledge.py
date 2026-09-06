from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class KnowledgeBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = "general"
    content: Optional[str] = None
    source_type: str = "note"
    tags: Optional[List[str]] = None
    metadata_json: Optional[dict] = None


class KnowledgeCreate(KnowledgeBase):
    pass


class KnowledgeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    source_type: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[dict] = None


class KnowledgeResponse(KnowledgeBase):
    id: UUID
    status: str = "active"
    file_path: Optional[str] = None
    chunk_count: Optional[str] = None
    embedding_id: Optional[str] = None
    embedding_dimensions: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentKnowledgeAccessResponse(BaseModel):
    id: UUID
    agent_id: UUID
    knowledge_id: UUID
    access_level: str
    granted_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    limit: int = 10


class AgentContextRequest(BaseModel):
    agent_id: UUID
    query: str


class BulkAccessRequest(BaseModel):
    agent_id: UUID
    knowledge_ids: List[UUID]
    access_level: str = "read"


class SourceCitation(BaseModel):
    citation_number: int
    knowledge_id: str
    source_name: str
    category: str
    score: float
    chunk_index: int = 0


class RAGContextResponse(BaseModel):
    context: str
    sources: List[SourceCitation]
    chunks: List[dict]
