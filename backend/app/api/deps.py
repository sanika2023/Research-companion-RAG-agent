import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (
    AgentSettings,
    DiagnosticsSettings,
    IngestSettings,
    RetrievalSettings,
    get_settings,
)
from app.db.session import get_session
from app.ingestion.store import get_document
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


def get_diagnostics_settings() -> DiagnosticsSettings:
    return get_settings().diagnostics


async def existing_paper(
    doc_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_session)]
) -> uuid.UUID:
    # A dependency, so a streaming endpoint can still answer 404 before the stream starts.
    if await get_document(session, doc_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return doc_id
