"""Fetch specific passages of a paper (for re-running an answer), outside of search."""

import random
import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk
from app.retrieval.hybrid import SearchHit


async def load_passages(
    session: AsyncSession, doc_id: uuid.UUID, chunk_ids: Sequence[uuid.UUID]
) -> list[SearchHit] | None:
    """The passages in the given order; None if any id isn't a passage of this paper."""
    rows = await session.execute(
        select(Chunk).where(Chunk.doc_id == doc_id, Chunk.id.in_(chunk_ids))
    )
    chunks = {c.id: c for c in rows.scalars()}
    if any(i not in chunks for i in chunk_ids):
        return None
    return [_passage(chunks[i]) for i in chunk_ids]


async def pick_distractor(
    session: AsyncSession, doc_id: uuid.UUID, *, exclude: Collection[uuid.UUID], seed: str
) -> SearchHit | None:
    """A random passage of the paper outside `exclude`; the same seed gives the same pick."""
    ids = await session.scalars(
        select(Chunk.id)
        .where(Chunk.doc_id == doc_id, Chunk.id.not_in(exclude))
        .order_by(Chunk.chunk_index)  # a stable order, so the seeded choice is repeatable
    )
    candidates = list(ids)
    if not candidates:
        return None
    chunk = await session.get_one(Chunk, random.Random(seed).choice(candidates))
    return _passage(chunk)


def _passage(chunk: Chunk) -> SearchHit:
    # Not a search result, so there is no score or rank to report.
    return SearchHit(
        chunk_id=chunk.id,
        doc_id=chunk.doc_id,
        page=chunk.page,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        bbox=chunk.bbox,
        score=0.0,
        keyword_rank=None,
        vector_rank=None,
    )
