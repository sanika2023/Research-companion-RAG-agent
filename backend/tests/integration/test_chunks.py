import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.retrieval.chunks import load_passages, pick_distractor
from tests.integration.seed import seed_paper

pytestmark = pytest.mark.integration

TEXTS = ["Intro.", "Method.", "Results.", "Appendix."]


async def test_load_passages_keeps_the_requested_order(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    wanted = [paper.chunk_ids[2], paper.chunk_ids[0]]

    async with AsyncSession(async_engine) as session:
        passages = await load_passages(session, paper.doc_id, wanted)

    assert passages is not None
    assert [p.text for p in passages] == ["Results.", "Intro."]
    assert [p.page for p in passages] == [3, 1]


async def test_load_passages_rejects_a_passage_from_another_paper(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    other = await seed_paper(async_engine, ["Elsewhere."], filename="other.pdf")

    async with AsyncSession(async_engine) as session:
        passages = await load_passages(
            session, paper.doc_id, [paper.chunk_ids[0], other.chunk_ids[0]]
        )

    assert passages is None


async def test_load_passages_rejects_an_unknown_id(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    async with AsyncSession(async_engine) as session:
        assert await load_passages(session, paper.doc_id, [uuid.uuid4()]) is None


async def test_pick_distractor_never_picks_a_passage_the_model_already_saw(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    seen = paper.chunk_ids[:3]

    async with AsyncSession(async_engine) as session:
        distractor = await pick_distractor(session, paper.doc_id, exclude=seen, seed="q")

    assert distractor is not None
    assert distractor.text == "Appendix."


async def test_pick_distractor_stays_within_the_paper(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    await seed_paper(async_engine, ["Other paper."], filename="other.pdf")

    async with AsyncSession(async_engine) as session:
        distractor = await pick_distractor(session, paper.doc_id, exclude=paper.chunk_ids, seed="q")

    assert distractor is None  # every passage of this paper was already shown


async def test_pick_distractor_is_repeatable_for_the_same_seed(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    async with AsyncSession(async_engine) as session:
        picks = [
            await pick_distractor(session, paper.doc_id, exclude=[], seed="same q")
            for _ in range(5)
        ]

    assert picks[0] is not None
    assert all(p == picks[0] for p in picks)
