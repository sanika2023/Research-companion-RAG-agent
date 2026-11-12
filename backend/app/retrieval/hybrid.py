import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk
from app.llm.base import Embedder
from app.retrieval.fusion import Fused, reciprocal_rank_fusion
from app.retrieval.lexical import keyword_search
from app.retrieval.vector import vector_search


@dataclass(frozen=True)
class SearchHit:
    chunk_id: uuid.UUID
    doc_id: uuid.UUID
    page: int
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    bbox: list[list[float]]
    score: float  # RRF score; only meaningful for ordering within one search
    # Why it was retrieved (1-based; None = not in that list). Kept for auditing.
    keyword_rank: int | None
    vector_rank: int | None


async def hybrid_search(
    session: AsyncSession,
    embedder: Embedder,
    doc_id: uuid.UUID,
    query: str,
    *,
    top_k: int,
    candidates: int,
    rrf_k: int,
) -> list[SearchHit]:
    """Keyword + vector search over one paper, fused with Reciprocal Rank Fusion."""
    [query_vector] = await embedder.embed([query])
    # Same session, so sequential: an AsyncSession can't run two queries at once.
    keyword_ids = await keyword_search(session, doc_id, query, limit=candidates)
    vector_ids = await vector_search(session, doc_id, query_vector, limit=candidates)

    fused = reciprocal_rank_fusion([keyword_ids, vector_ids], k=rrf_k)[:top_k]
    if not fused:
        return []

    rows = await session.execute(select(Chunk).where(Chunk.id.in_([f.id for f in fused])))
    chunks = {c.id: c for c in rows.scalars()}
    return [_hit(chunks[f.id], f) for f in fused]


def _hit(chunk: Chunk, fused: Fused[uuid.UUID]) -> SearchHit:
    keyword_rank, vector_rank = fused.ranks
    return SearchHit(
        chunk_id=chunk.id,
        doc_id=chunk.doc_id,
        page=chunk.page,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        bbox=chunk.bbox,
        score=fused.score,
        keyword_rank=keyword_rank,
        vector_rank=vector_rank,
    )
