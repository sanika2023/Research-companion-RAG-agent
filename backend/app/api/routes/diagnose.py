import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import existing_paper, get_diagnostics_settings, get_embedder, get_llm
from app.api.routes.ask import UNAVAILABLE
from app.core.config import DiagnosticsSettings
from app.db.session import get_session
from app.diagnostics.inspector import Original, inspect
from app.llm.base import Embedder, LLMClient
from app.llm.gemini import LLMUnavailableError
from app.retrieval.chunks import load_passages, pick_distractor
from app.schemas.diagnose import DiagnoseRequest, DiagnoseResponse, SignalOut

router = APIRouter(prefix="/documents", tags=["diagnostics"])


@router.post("/{doc_id}/diagnose")
async def diagnose_answer(
    doc_id: Annotated[uuid.UUID, Depends(existing_paper)],
    request: DiagnoseRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    llm: Annotated[LLMClient, Depends(get_llm)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    settings: Annotated[DiagnosticsSettings, Depends(get_diagnostics_settings)],
) -> DiagnoseResponse:
    """Re-ask with controlled changes and score how much the answer moves (0-1).

    Slow (several model calls), so the client calls it after showing the answer.
    """
    passages = await load_passages(session, doc_id, request.passage_ids)
    if passages is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "passage_ids must be passages of this paper"
        )
    # Seeded by the question so re-inspecting the same answer picks the same distractor.
    distractor = await pick_distractor(
        session, doc_id, exclude=request.passage_ids, seed=request.question
    )
    original = Original(
        question=request.question,
        answer=request.answer,
        passages=passages,
        sub_questions=request.sub_questions,
    )
    try:
        report = await inspect(
            original, llm=llm, embedder=embedder, distractor=distractor, settings=settings
        )
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE) from exc
    return DiagnoseResponse(
        doc_id=doc_id,
        uncertainty=report.uncertainty,
        signals=[SignalOut(**asdict(s)) for s in report.signals],
        claims=report.claims,
        flags=report.flags,
    )
