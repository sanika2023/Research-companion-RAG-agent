import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.events import AgentEvent, Finished, StepStarted, SubQuestions, Token
from app.agent.graph import Agent
from app.agent.service import ask, ask_stream, paper_agent
from app.agent.state import AgentState
from app.api.deps import get_agent_settings, get_embedder, get_llm, get_retrieval_settings
from app.core.config import AgentSettings, RetrievalSettings
from app.db.session import get_session
from app.ingestion.store import get_document
from app.llm.base import Embedder, LLMClient
from app.llm.gemini import LLMUnavailableError
from app.schemas.ask import AskRequest, AskResponse, CitationOut

router = APIRouter(prefix="/documents", tags=["ask"])
log = logging.getLogger(__name__)

UNAVAILABLE = "The language model is busy or unavailable right now. Please try again shortly."
FAILED = "Something went wrong while answering. Please try again."


async def existing_paper(
    doc_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_session)]
) -> uuid.UUID:
    # A dependency, so a streaming endpoint can still answer 404 before the stream starts.
    if await get_document(session, doc_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return doc_id


async def agent_for_paper(
    doc_id: Annotated[uuid.UUID, Depends(existing_paper)],
    session: Annotated[AsyncSession, Depends(get_session)],
    llm: Annotated[LLMClient, Depends(get_llm)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    retrieval: Annotated[RetrievalSettings, Depends(get_retrieval_settings)],
    agent_settings: Annotated[AgentSettings, Depends(get_agent_settings)],
) -> Agent:
    return paper_agent(
        doc_id=doc_id,
        session=session,
        llm=llm,
        embedder=embedder,
        retrieval=retrieval,
        agent_settings=agent_settings,
    )


@router.post("/{doc_id}/ask")
async def ask_document(
    doc_id: uuid.UUID, request: AskRequest, agent: Annotated[Agent, Depends(agent_for_paper)]
) -> AskResponse:
    """Answer a question about one paper, citing the passages (and pages) it relied on."""
    try:
        result = await ask(request.question, agent)
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE) from exc
    return _response(doc_id, request.question, result)


@router.post("/{doc_id}/ask/stream", response_class=EventSourceResponse)
async def ask_document_stream(
    doc_id: uuid.UUID, request: AskRequest, agent: Annotated[Agent, Depends(agent_for_paper)]
) -> AsyncIterator[ServerSentEvent]:
    """Like /ask, but streams progress and answer tokens as Server-Sent Events.

    Events: `status` (step started), `sub_questions`, `token` (raw answer text), then `done`
    (the citation-checked answer, same shape as /ask, which replaces the streamed text) or
    `error`.
    """
    try:
        async for event in ask_stream(request.question, agent):
            yield _to_sse(doc_id, request.question, event)
    # The 200 status is already sent, so failures can only be reported in-stream; the client
    # must always get a final `done` or `error` rather than a stream that just stops.
    except LLMUnavailableError:
        yield ServerSentEvent(event="error", data={"message": UNAVAILABLE})
    except Exception:
        log.exception("ask stream failed for document %s", doc_id)
        yield ServerSentEvent(event="error", data={"message": FAILED})


def _to_sse(doc_id: uuid.UUID, question: str, event: AgentEvent) -> ServerSentEvent:
    match event:
        case StepStarted(step):
            return ServerSentEvent(event="status", data={"step": step})
        case SubQuestions(questions):
            return ServerSentEvent(event="sub_questions", data={"sub_questions": questions})
        case Token(text):
            return ServerSentEvent(event="token", data={"text": text})
        case Finished(state):
            done = _response(doc_id, question, state).model_dump(mode="json")
            return ServerSentEvent(event="done", data=done)


def _response(doc_id: uuid.UUID, question: str, result: AgentState) -> AskResponse:
    return AskResponse(
        doc_id=doc_id,
        question=question,
        answer=result["answer"],
        citations=[CitationOut(**asdict(c)) for c in result["citations"]],
        refused=result["refused"],
        sub_questions=result.get("sub_questions", []),
        flags=result["flags"],
    )
