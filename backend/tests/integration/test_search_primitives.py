"""Keyword and vector search, each scoped to a single paper."""

import math
import random

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.retrieval.lexical import keyword_search
from app.retrieval.vector import vector_search
from tests.conftest import FakeEmbedder
from tests.integration.seed import seed_paper

pytestmark = pytest.mark.integration

TEXTS = [
    "Hallucination detection with metamorphic relations.",
    "Vision language models answer visual questions.",
    "Uncertainty quantification for neural networks.",
]


def _nudge(vector: list[float], seed: int) -> list[float]:
    """A distinct unit vector very close to `vector`."""
    rng = random.Random(seed)
    nudged = [x + rng.gauss(0, 0.01) for x in vector]
    norm = math.sqrt(sum(x * x for x in nudged))
    return [x / norm for x in nudged]


# --- keyword search ---------------------------------------------------------------------


async def test_keyword_search_finds_chunk_containing_the_term(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    async with AsyncSession(async_engine) as session:
        ids = await keyword_search(session, paper.doc_id, "metamorphic", limit=10)

    assert ids == [paper.chunk_ids[0]]


async def test_keyword_search_matches_word_stems(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    async with AsyncSession(async_engine) as session:
        ids = await keyword_search(session, paper.doc_id, "hallucinations detected", limit=10)

    assert ids == [paper.chunk_ids[0]]


async def test_keyword_search_matches_any_term_and_ranks_more_matches_first(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    async with AsyncSession(async_engine) as session:
        # Question-style query: no chunk contains every word.
        ids = await keyword_search(
            session, paper.doc_id, "How do vision models handle uncertainty?", limit=10
        )

    # Chunk 1 matches "vision" + "models"; chunk 2 matches only "uncertainty".
    assert ids == [paper.chunk_ids[1], paper.chunk_ids[2]]


async def test_keyword_search_only_searches_the_selected_paper(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    selected = await seed_paper(async_engine, TEXTS)
    other = await seed_paper(async_engine, ["Metamorphic testing of compilers."])

    async with AsyncSession(async_engine) as session:
        ids = await keyword_search(session, selected.doc_id, "metamorphic", limit=10)

    assert other.chunk_ids[0] not in ids
    assert ids == [selected.chunk_ids[0]]


@pytest.mark.parametrize("query", ["the of and", "", "C++ & (a:b) | !x 'quoted'"])
async def test_keyword_search_tolerates_stopwords_and_punctuation(
    sync_engine: Engine, async_engine: AsyncEngine, query: str
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    async with AsyncSession(async_engine) as session:
        ids = await keyword_search(session, paper.doc_id, query, limit=10)

    assert isinstance(ids, list)  # no SQL syntax error from user input


# --- vector search ----------------------------------------------------------------------


async def test_vector_search_ranks_identical_text_first(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    [query_vector] = await FakeEmbedder().embed([TEXTS[2]])

    async with AsyncSession(async_engine) as session:
        ids = await vector_search(session, paper.doc_id, query_vector, limit=10)

    assert ids[0] == paper.chunk_ids[2]
    assert sorted(ids) == sorted(paper.chunk_ids)  # every chunk is a candidate


async def test_vector_search_respects_the_limit(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    [query_vector] = await FakeEmbedder().embed(["anything"])

    async with AsyncSession(async_engine) as session:
        ids = await vector_search(session, paper.doc_id, query_vector, limit=2)

    assert len(ids) == 2


async def test_vector_search_finds_selected_paper_even_when_others_are_closer(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    [query_vector] = await FakeEmbedder().embed(["shared query text"])
    # 60 distinct chunks in another paper, all much closer to the query than the selected
    # paper's chunks: they would fill an approximate index's candidate list.
    crowd = [_nudge(query_vector, seed) for seed in range(60)]
    await seed_paper(async_engine, ["crowd"] * 60, filename="crowd.pdf", vectors=crowd)
    selected = await seed_paper(async_engine, TEXTS)

    async with AsyncSession(async_engine) as session:
        # Small tables never use HNSW; force it so this test covers the large-corpus path.
        for setting in ("enable_seqscan", "enable_bitmapscan", "enable_sort"):
            await session.execute(text(f"SET LOCAL {setting} = off"))
        ids = await vector_search(session, selected.doc_id, query_vector, limit=10)

    assert sorted(ids) == sorted(selected.chunk_ids)
