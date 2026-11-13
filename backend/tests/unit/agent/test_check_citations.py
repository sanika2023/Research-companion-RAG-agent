from app.agent.nodes.check_citations import NOT_FOUND_MESSAGE, check_citations
from app.agent.prompts import NOT_FOUND
from app.agent.state import AgentState
from tests.unit.agent.helpers import hit

PASSAGES = [hit("alpha", page=2), hit("beta", page=5), hit("gamma", page=9)]


def state_with(draft: str) -> AgentState:
    return {"question": "q", "passages": PASSAGES, "draft": draft}


def test_citations_map_to_passages_in_order_of_first_use() -> None:
    update = check_citations(state_with("B is true [2]. A too [1]. Again [2]."))

    assert [(c.number, c.page, c.text) for c in update["citations"]] == [
        (2, 5, "beta"),
        (1, 2, "alpha"),
    ]
    assert update["answer"] == "B is true [2]. A too [1]. Again [2]."
    assert update["refused"] is False


def test_grouped_citations_are_understood() -> None:
    update = check_citations(state_with("Both hold [1, 3]."))

    assert [c.number for c in update["citations"]] == [1, 3]


def test_citations_to_passages_that_dont_exist_are_removed_and_flagged() -> None:
    update = check_citations(state_with("Real [1]. Invented [7]. Mixed [3, 9]."))

    assert update["answer"] == "Real [1]. Invented. Mixed [3]."
    assert [c.number for c in update["citations"]] == [1, 3]
    assert "invalid_citations_removed" in update["flags"]


def test_answer_without_any_valid_citation_is_flagged() -> None:
    update = check_citations(state_with("A confident claim with no source."))

    assert update["citations"] == []
    assert "uncited" in update["flags"]


def test_not_found_reply_becomes_a_refusal() -> None:
    update = check_citations(state_with(f"  {NOT_FOUND}\n"))

    assert update["refused"] is True
    assert update["answer"] == NOT_FOUND_MESSAGE
    assert update["citations"] == []
