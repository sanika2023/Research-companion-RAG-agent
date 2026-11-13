from app.agent.nodes.retrieve import make_retrieve
from tests.unit.agent.helpers import FakeSearch, hit


async def test_simple_question_is_searched_once() -> None:
    search = FakeSearch({"q": [hit("a"), hit("b")]})

    update = await make_retrieve(search, max_passages=10)({"question": "q"})

    assert search.queries == ["q"]
    assert [p.text for p in update["passages"]] == ["a", "b"]


async def test_question_and_each_sub_question_are_searched() -> None:
    search = FakeSearch({})

    await make_retrieve(search, max_passages=10)({"question": "q", "sub_questions": ["s1", "s2"]})

    assert search.queries == ["q", "s1", "s2"]


async def test_results_are_interleaved_deduplicated_and_capped() -> None:
    # Interleaving gives every sub-question a share of the limited passage budget.
    search = FakeSearch(
        {
            "q": [hit("q1"), hit("shared"), hit("q3")],
            "s": [hit("shared"), hit("s2"), hit("s3")],
        }
    )

    update = await make_retrieve(search, max_passages=4)({"question": "q", "sub_questions": ["s"]})

    assert [p.text for p in update["passages"]] == ["q1", "shared", "s2", "q3"]
