import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk


async def vector_search(
    session: AsyncSession, doc_id: uuid.UUID, query_vector: list[float], limit: int
) -> list[uuid.UUID]:
    """Chunk ids of one paper ranked by cosine similarity to the query vector (exact)."""
    # The chunk_index tie-breaker means the HNSW index cannot supply this ordering, so Postgres
    # filters by doc_id and sorts that paper's ~100 chunks exactly. That's deliberate: HNSW
    # filters *after* its approximate search, so other papers could crowd this one out.
    rows = await session.execute(
        select(Chunk.id)
        .where(Chunk.doc_id == doc_id)
        .order_by(Chunk.embedding.cosine_distance(query_vector), Chunk.chunk_index)
        .limit(limit)
    )
    return list(rows.scalars())
