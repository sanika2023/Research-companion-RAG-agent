import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.ingestion.chunk import Chunk


async def add_document(
    session: AsyncSession,
    filename: str,
    page_count: int,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    pdf: bytes,
) -> models.Document:
    """Stage a document, its chunks, and its PDF; the caller decides when to commit."""
    doc = models.Document(filename=filename, page_count=page_count)
    doc.chunks = [
        models.Chunk(
            page=c.page,
            chunk_index=c.chunk_index,
            text=c.text,
            char_start=c.char_start,
            char_end=c.char_end,
            bbox=c.bbox,
            embedding=vector,
        )
        for c, vector in zip(chunks, embeddings, strict=True)
    ]
    session.add(doc)
    await session.flush()  # assigns doc.id without ending the transaction
    session.add(models.DocumentFile(doc_id=doc.id, data=pdf))
    return doc


async def list_documents(session: AsyncSession) -> list[tuple[models.Document, int]]:
    """Every document with its chunk count, newest first."""
    chunk_count = func.count(models.Chunk.id)
    rows = await session.execute(
        select(models.Document, chunk_count)
        .outerjoin(models.Chunk)
        .group_by(models.Document.id)
        .order_by(models.Document.created_at.desc())
    )
    return [(doc, count) for doc, count in rows.tuples()]


async def get_document(session: AsyncSession, doc_id: uuid.UUID) -> models.Document | None:
    return await session.get(models.Document, doc_id)


async def get_pdf(session: AsyncSession, doc_id: uuid.UUID) -> bytes | None:
    return await session.scalar(
        select(models.DocumentFile.data).where(models.DocumentFile.doc_id == doc_id)
    )
