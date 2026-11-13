import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.service import ask
from app.api.deps import get_agent_settings, get_embedder, get_llm, get_retrieval_settings
from app.core.config import AgentSettings, RetrievalSettings
from app.db.session import get_session
from app.ingestion.store import get_document
from app.llm.base import Embedder, LLMClient
from app.llm.gemini import LLMUnavailableError
from app.schemas.ask import AskRequest, AskResponse, CitationOut

router = APIRouter(prefix="/documents", tags=["ask"])


@router.post("/{doc_id}/ask")
async def ask_document(
    doc_id: uuid.UUID,
    request: AskRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    llm: Annotated[LLMClient, Depends(get_llm)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    retrieval: Annotated[RetrievalSettings, Depends(get_retrieval_settings)],
    agent_settings: Annotated[AgentSettings, Depends(get_agent_settings)],
) -> AskResponse:
    """Answer a question about one paper, citing the passages (and pages) it relied on."""
    if await get_document(session, doc_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    try:
        result = await ask(
            request.question,
            doc_id=doc_id,
            session=session,
            llm=llm,
            embedder=embedder,
            retrieval=retrieval,
            agent_settings=agent_settings,
        )
    except LLMUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The language model is busy or unavailable right now. Please try again shortly.",
        ) from exc

    return AskResponse(
        doc_id=doc_id,
        question=request.question,
        answer=result["answer"],
        citations=[CitationOut(**asdict(c)) for c in result["citations"]],
        refused=result["refused"],
        sub_questions=result.get("sub_questions", []),
        flags=result["flags"],
    )
