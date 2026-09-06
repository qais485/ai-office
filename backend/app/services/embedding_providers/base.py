"""Abstract base class for embedding providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class EmbeddingResult:
    """Result from an embedding API call."""
    embeddings: List[List[float]]
    model: str
    dimensions: int
    usage: Optional[Dict[str, Any]] = field(default_factory=dict)


class EmbeddingProvider(ABC):
    """Base class that every embedding provider must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the canonical provider name (e.g. 'openai')."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model identifier."""
        ...

    @property
    @abstractmethod
    def default_dimensions(self) -> int:
        """Return the default embedding dimensions."""
        ...

    @abstractmethod
    async def embed_texts(
        self,
        texts: List[str],
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> EmbeddingResult:
        """Embed a batch of texts.

        Parameters
        ----------
        texts:
            List of text strings to embed.
        model:
            Model override (provider default if None).
        dimensions:
            Dimension override (provider default if None).

        Returns
        -------
        EmbeddingResult
        """
        ...

    @abstractmethod
    async def embed_query(self, text: str, model: Optional[str] = None) -> List[float]:
        """Embed a single query text (convenience wrapper)."""
        ...
