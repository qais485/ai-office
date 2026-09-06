"""Tests for embedding providers."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.embedding_providers.base import EmbeddingProvider, EmbeddingResult
from app.services.embedding_providers.registry import get_embedding_provider, _lazy_load_provider
from app.services.embedding_providers.openai_provider import OpenAIEmbeddingProvider


class TestEmbeddingResult:
    def test_creation(self):
        result = EmbeddingResult(
            embeddings=[[0.1, 0.2, 0.3]],
            model="test-model",
            dimensions=3,
            usage={"tokens": 10},
        )
        assert len(result.embeddings) == 1
        assert result.model == "test-model"
        assert result.dimensions == 3

    def test_empty_embeddings(self):
        result = EmbeddingResult(embeddings=[], model="m", dimensions=128)
        assert result.embeddings == []


class TestOpenAIEmbeddingProvider:
    def test_init_defaults(self):
        with patch("app.services.embedding_providers.openai_provider.settings") as mock_settings:
            mock_settings.EMBEDDING_API_KEY = "test-key"
            mock_settings.EMBEDDING_BASE_URL = "https://api.openai.com/v1"
            mock_settings.EMBEDDING_MODEL = "text-embedding-3-small"
            mock_settings.EMBEDDING_DIMENSIONS = 1536

            provider = OpenAIEmbeddingProvider()
            assert provider.provider_name == "openai"
            assert provider.default_model == "text-embedding-3-small"
            assert provider.default_dimensions == 1536

    def test_init_custom(self):
        provider = OpenAIEmbeddingProvider(
            api_key="custom-key",
            base_url="https://custom.api.com/v1",
        )
        assert provider._api_key == "custom-key"
        assert provider._base_url == "https://custom.api.com/v1"

    @pytest.mark.asyncio
    async def test_embed_texts_success(self):
        provider = OpenAIEmbeddingProvider(api_key="test-key", base_url="https://api.test.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3], "index": 0},
                {"embedding": [0.4, 0.5, 0.6], "index": 1},
            ],
            "model": "text-embedding-3-small",
            "usage": {"total_tokens": 10},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.embed_texts(["hello", "world"])

        assert len(result.embeddings) == 2
        assert result.embeddings[0] == [0.1, 0.2, 0.3]
        assert result.embeddings[1] == [0.4, 0.5, 0.6]
        assert result.model == "text-embedding-3-small"

    @pytest.mark.asyncio
    async def test_embed_texts_empty(self):
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        result = await provider.embed_texts([])
        assert result.embeddings == []

    @pytest.mark.asyncio
    async def test_embed_texts_preserves_order(self):
        provider = OpenAIEmbeddingProvider(api_key="test-key", base_url="https://api.test.com")

        # Response data is intentionally out of order
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.4, 0.5, 0.6], "index": 1},
                {"embedding": [0.1, 0.2, 0.3], "index": 0},
            ],
            "model": "text-embedding-3-small",
            "usage": {"total_tokens": 10},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.embed_texts(["hello", "world"])

        # Should be sorted by index: [0.1,0.2,0.3] first, then [0.4,0.5,0.6]
        assert result.embeddings[0] == [0.1, 0.2, 0.3]
        assert result.embeddings[1] == [0.4, 0.5, 0.6]

    @pytest.mark.asyncio
    async def test_embed_query(self):
        provider = OpenAIEmbeddingProvider(api_key="test-key", base_url="https://api.test.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}],
            "model": "text-embedding-3-small",
            "usage": {"total_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.embed_query("test query")

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_texts_api_error(self):
        provider = OpenAIEmbeddingProvider(api_key="test-key", base_url="https://api.test.com")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="401 Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError):
                await provider.embed_texts(["test"])


class TestEmbeddingRegistry:
    def test_get_provider_default(self):
        with patch("app.services.embedding_providers.registry.settings") as mock_settings:
            mock_settings.EMBEDDING_PROVIDER = "openai"
            mock_settings.EMBEDDING_API_KEY = "test-key"
            mock_settings.EMBEDDING_BASE_URL = "https://api.openai.com/v1"
            mock_settings.EMBEDDING_MODEL = "text-embedding-3-small"
            mock_settings.EMBEDDING_DIMENSIONS = 1536

            # Clear registry to force lazy loading
            from app.services.embedding_providers import registry
            registry._registry.clear()

            provider = get_embedding_provider()
            assert provider.provider_name == "openai"

    def test_get_provider_unknown(self):
        from app.services.embedding_providers import registry
        registry._registry.clear()

        with patch("app.services.embedding_providers.registry.settings") as mock_settings:
            mock_settings.EMBEDDING_PROVIDER = "nonexistent"
            with pytest.raises(ValueError, match="Unknown embedding provider"):
                get_embedding_provider("nonexistent")
