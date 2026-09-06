"""OpenAI-compatible embedding provider.

Works with OpenAI, OpenRouter, Together, Groq, and any API
that implements the OpenAI /v1/embeddings endpoint.
"""
import asyncio
import logging
from typing import List, Optional

import httpx

from app.core.config import settings
from app.services.embedding_providers.base import EmbeddingProvider, EmbeddingResult

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider for OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self._api_key = api_key or settings.EMBEDDING_API_KEY
        self._base_url = (base_url or settings.EMBEDDING_BASE_URL).rstrip("/")
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return settings.EMBEDDING_MODEL

    @property
    def default_dimensions(self) -> int:
        return settings.EMBEDDING_DIMENSIONS

    async def embed_texts(
        self,
        texts: List[str],
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
    ) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(embeddings=[], model=model or self.default_model, dimensions=dimensions or self.default_dimensions)

        if not self._api_key:
            raise ValueError(
                "EMBEDDING_API_KEY is not set. "
                "Please set the EMBEDDING_API_KEY environment variable."
            )

        model = model or self.default_model
        dimensions = dimensions or self.default_dimensions

        logger.debug("Embedding %d texts with model=%s dims=%s", len(texts), model, dimensions)
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload: dict = {
            "model": model,
            "input": texts,
        }
        if dimensions:
            payload["dimensions"] = dimensions

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except Exception:
            logger.error("OpenAI embedding API call failed", exc_info=True)
            raise

        data = response.json()
        logger.debug("Embedding response: model=%s usage=%s", data.get("model"), data.get("usage"))
        # Sort by index to preserve ordering
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        embeddings = [item["embedding"] for item in sorted_data]

        return EmbeddingResult(
            embeddings=embeddings,
            model=data.get("model", model),
            dimensions=len(embeddings[0]) if embeddings else dimensions,
            usage=data.get("usage"),
        )

    async def embed_query(self, text: str, model: Optional[str] = None) -> List[float]:
        result = await self.embed_texts([text], model=model)
        return result.embeddings[0] if result.embeddings else []
