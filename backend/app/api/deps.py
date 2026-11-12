from functools import lru_cache

from app.core.config import IngestSettings, RetrievalSettings, get_settings
from app.llm.base import Embedder
from app.llm.embeddings import FastEmbedEmbedder


@lru_cache
def get_embedder() -> Embedder:
    # One model instance per process; loading it per request would take seconds.
    settings = get_settings()
    return FastEmbedEmbedder(settings.embedding_model, cache_dir=settings.embedding_cache_dir)


def get_ingest_settings() -> IngestSettings:
    return get_settings().ingest


def get_retrieval_settings() -> RetrievalSettings:
    return get_settings().retrieval
