import asyncio
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.chunk import Chunk, chunk_pages
from app.ingestion.parse import parse_pdf
from app.ingestion.store import add_document
from app.llm.base import Embedder


class NoTextError(ValueError):
    """The PDF has no text layer (e.g. a scanned paper); we don't OCR."""


@dataclass(frozen=True)
class IngestResult:
    doc_id: uuid.UUID
    page_count: int
    chunk_count: int


async def ingest_pdf(
    data: bytes,
    filename: str,
    *,
    session: AsyncSession,
    embedder: Embedder,
    upload_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
) -> IngestResult:
    """PDF bytes -> parsed pages -> chunks -> embeddings -> one DB transaction + saved file."""
    # Parsing is CPU-bound; keep it off the event loop.
    page_count, chunks = await asyncio.to_thread(_parse_and_chunk, data, chunk_size, chunk_overlap)
    if not chunks:
        raise NoTextError("PDF contains no extractable text")

    embeddings = await embedder.embed([c.text for c in chunks])

    try:
        doc = await add_document(session, filename, page_count, chunks, embeddings)
        doc_id = doc.id  # read before commit: commit expires attributes, and async can't reload
        # File first, commit last: if the write fails, the rollback leaves no orphan rows.
        await asyncio.to_thread(_save_pdf, upload_dir, doc_id, data)
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    return IngestResult(doc_id=doc_id, page_count=page_count, chunk_count=len(chunks))


def _parse_and_chunk(data: bytes, size: int, overlap: int) -> tuple[int, list[Chunk]]:
    parsed = parse_pdf(data)
    return parsed.page_count, chunk_pages(parsed.pages, size=size, overlap=overlap)


def pdf_path(upload_dir: Path, doc_id: uuid.UUID) -> Path:
    """Where a paper's original PDF is kept (the only place that decides this)."""
    return upload_dir / f"{doc_id}.pdf"


def _save_pdf(upload_dir: Path, doc_id: uuid.UUID, data: bytes) -> None:
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path(upload_dir, doc_id).write_bytes(data)
