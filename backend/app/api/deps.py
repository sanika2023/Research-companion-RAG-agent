from functools import lru_cache

from app.core.config import AgentSettings, IngestSettings, RetrievalSettings, get_settings
from app.llm.base import Embedder, LLMClient
from app.llm.embeddings import FastEmbedEmbedder
from app.llm.gemini import create_gemini_client


@lru_cache
def get_embedder() -> Embedder:
    # One model instance per process; loading it per request would take seconds.
    settings = get_settings()
    return FastEmbedEmbedder(settings.embedding_model, cache_dir=settings.embedding_cache_dir)


@lru_cache
def get_llm() -> LLMClient:
    settings = get_settings()
    return create_gemini_client(
        settings.llm_api_key.get_secret_value(),
        answer_model=settings.llm_answer_model,
        light_model=settings.llm_light_model,
        timeout_s=settings.llm_timeout_s,
    )


def get_ingest_settings() -> IngestSettings:
    return get_settings().ingest


def get_retrieval_settings() -> RetrievalSettings:
    return get_settings().retrieval


def get_agent_settings() -> AgentSettings:
    return get_settings().agent
