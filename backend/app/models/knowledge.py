import enum
from sqlalchemy import Column, String, ForeignKey, Text, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class KnowledgeStatus(str, enum.Enum):
    ACTIVE = "active"
    PROCESSING = "processing"
    INACTIVE = "inactive"
    ERROR = "error"


class SourceType(str, enum.Enum):
    PDF = "pdf"
    DOCUMENT = "document"
    TEXT = "text"
    URL = "url"
    NOTE = "note"
    FAQ = "faq"


class KnowledgeCategory(str, enum.Enum):
    PRODUCTS = "products"
    SERVICES = "services"
    PRICING = "pricing"
    POLICIES = "policies"
    FAQ = "faq"
    BRAND_VOICE = "brand_voice"
    INTERNAL_DOCUMENTS = "internal_documents"
    CUSTOMER_INFO = "customer_info"
    GENERAL = "general"


class KnowledgeSource(BaseModel):
    __tablename__ = "knowledge_sources"

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default=KnowledgeCategory.GENERAL.value)
    content = Column(Text, nullable=True)
    source_type = Column(String(20), nullable=False, default=SourceType.NOTE.value)
    status = Column(String(20), nullable=False, default=KnowledgeStatus.ACTIVE.value)
    file_path = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=True)
    chunk_count = Column(String(10), nullable=True, default="0")
    embedding_id = Column(String(100), nullable=True)
    embedding_dimensions = Column(String(10), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
