"""Embedding provider registry."""
from typing import Dict, Optional

from app.core.config import settings
from app.services.embedding_providers.base import EmbeddingProvider


_registry: Dict[str, EmbeddingProvider] = {}


def get_embedding_provider(name: Optional[str] = None) -> EmbeddingProvider:
    """Get an embedding provider by name, or the configured default."""
    name = name or settings.EMBEDDING_PROVIDER

    if name not in _registry:
        _lazy_load_provider(name)

    provider = _registry.get(name)
    if provider is None:
        raise ValueError(f"Unknown embedding provider: {name}")
    return provider


def register_embedding_provider(name: str, provider: EmbeddingProvider) -> None:
    _registry[name] = provider


def _lazy_load_provider(name: str) -> None:
    if name == "openai":
        from app.services.embedding_providers.openai_provider import OpenAIEmbeddingProvider
        _registry["openai"] = OpenAIEmbeddingProvider()
    else:
        raise ValueError(f"Unknown embedding provider: {name}")
