from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import settings


@lru_cache
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY or None,
        base_url=settings.LLM_BASE_URL,
        temperature=0.7,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
