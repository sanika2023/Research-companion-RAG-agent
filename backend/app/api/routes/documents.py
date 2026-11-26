import uuid
from dataclasses import asdict
from pathlib import PurePath
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_embedder, get_ingest_settings, get_retrieval_settings
from app.core.config import IngestSettings, RetrievalSettings
from app.db.session import get_session
from app.ingestion.parse import InvalidPDFError
from app.ingestion.pipeline import NoTextError, ingest_pdf
from app.ingestion.store import get_document, get_pdf, list_documents
from app.llm.base import Embedder
from app.retrieval.hybrid import hybrid_search
from app.schemas.documents import DocumentSummary, DocumentUploaded
from app.schemas.search import SearchHitOut, SearchRequest, SearchResponse

router = APIRouter(prefix="/documents", tags=["documents"])

Session = Annotated[AsyncSession, Depends(get_session)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
IngestSettingsDep = Annotated[IngestSettings, Depends(get_ingest_settings)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    session: Session,
    embedder: EmbedderDep,
    settings: IngestSettingsDep,
) -> DocumentUploaded:
    if not settings.allow_uploads:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "uploads are turned off on this server")
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)  # one extra byte tells us the file is too big
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"PDF larger than {settings.max_upload_mb} MB"
        )
    # Client-supplied names can carry paths ("../../x.pdf"); keep only the last part.
    filename = PurePath((file.filename or "upload.pdf").replace("\\", "/")).name

    try:
        result = await ingest_pdf(
            data,
            filename,
            session=session,
            embedder=embedder,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
    except (InvalidPDFError, NoTextError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    return DocumentUploaded(
        doc_id=result.doc_id,
        filename=filename,
        page_count=result.page_count,
        chunk_count=result.chunk_count,
    )


@router.get("")
async def get_documents(session: Session) -> list[DocumentSummary]:
    return [
        DocumentSummary(
            doc_id=doc.id,
            filename=doc.filename,
            page_count=doc.page_count,
            chunk_count=chunk_count,
            created_at=doc.created_at,
        )
        for doc, chunk_count in await list_documents(session)
    ]


@router.get("/{doc_id}/file", response_class=Response)
async def get_document_file(doc_id: uuid.UUID, session: Session) -> Response:
    """The original PDF, for the viewer."""
    doc = await get_document(session, doc_id)
    pdf = None if doc is None else await get_pdf(session, doc_id)
    if doc is None or pdf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.filename)}"},
    )


@router.post("/{doc_id}/search")
async def search_document(
    doc_id: uuid.UUID,
    request: SearchRequest,
    session: Session,
    embedder: EmbedderDep,
    settings: Annotated[RetrievalSettings, Depends(get_retrieval_settings)],
) -> SearchResponse:
    """Hybrid search within one paper; each hit reports its keyword and vector rank."""
    if await get_document(session, doc_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    hits = await hybrid_search(
        session,
        embedder,
        doc_id,
        request.query,
        top_k=request.top_k or settings.top_k,
        candidates=settings.candidates,
        rrf_k=settings.rrf_k,
    )
    return SearchResponse(
        doc_id=doc_id, query=request.query, hits=[SearchHitOut(**asdict(h)) for h in hits]
    )
