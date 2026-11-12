import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.retrieval.hybrid import SearchHit, hybrid_search
from tests.conftest import FakeEmbedder
from tests.integration.seed import seed_paper

pytestmark = pytest.mark.integration

TEXTS = [
    "Hallucination detection with metamorphic relations.",
    "Vision language models answer visual questions.",
    "Uncertainty quantification for neural networks.",
]


async def search(
    engine: AsyncEngine, doc_id: uuid.UUID, query: str, top_k: int = 10
) -> list[SearchHit]:
    async with AsyncSession(engine) as session:
        return await hybrid_search(
            session,
            FakeEmbedder(),
            doc_id,
            query,
            top_k=top_k,
            candidates=40,
            rrf_k=60,
        )


async def test_chunk_found_by_both_searches_ranks_first(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    # Identical text: rank 1 for the fake embedder and the only keyword match.
    [top, *_] = await search(async_engine, paper.doc_id, TEXTS[2])

    assert top.chunk_id == paper.chunk_ids[2]
    assert (top.keyword_rank, top.vector_rank) == (1, 1)


async def test_hits_carry_provenance_for_citations(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    [top, *_] = await search(async_engine, paper.doc_id, TEXTS[1])

    assert (top.doc_id, top.page, top.chunk_index, top.text) == (paper.doc_id, 2, 1, TEXTS[1])
    assert (top.char_start, top.char_end) == (0, len(TEXTS[1]))
    assert top.bbox == [[0.0, 0.0, 1.0, 1.0]]


async def test_vector_only_hits_have_no_keyword_rank(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    hits = await search(async_engine, paper.doc_id, "metamorphic")

    by_id = {h.chunk_id: h for h in hits}
    assert by_id[paper.chunk_ids[0]].keyword_rank == 1
    assert by_id[paper.chunk_ids[1]].keyword_rank is None
    assert by_id[paper.chunk_ids[1]].vector_rank is not None


async def test_scores_are_descending_and_top_k_is_respected(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    hits = await search(async_engine, paper.doc_id, "neural networks", top_k=2)

    assert len(hits) == 2
    assert hits[0].score >= hits[1].score


async def test_search_never_returns_other_papers(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    selected = await seed_paper(async_engine, TEXTS)
    await seed_paper(async_engine, ["Metamorphic relations everywhere."] * 5)

    hits = await search(async_engine, selected.doc_id, "metamorphic relations")

    assert {h.doc_id for h in hits} == {selected.doc_id}


async def test_unknown_paper_returns_no_hits(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    assert await search(async_engine, uuid.uuid4(), "anything") == []
