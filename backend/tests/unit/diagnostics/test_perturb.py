from app.diagnostics.perturb import add_distractor, drop_most_cited, reorder
from tests.unit.agent.helpers import hit

A, B, C = hit("a"), hit("b"), hit("c")


def test_reorder_reverses_the_passages() -> None:
    assert reorder([A, B, C]) == [C, B, A]


def test_reorder_leaves_the_original_list_untouched() -> None:
    passages = [A, B, C]

    reorder(passages)

    assert passages == [A, B, C]


def test_drop_most_cited_removes_the_passage_cited_most_often() -> None:
    answer = "X [2]. Y [1][2]. Z [2, 3]."

    assert drop_most_cited([A, B, C], answer) == [A, C]


def test_drop_most_cited_breaks_ties_by_first_use() -> None:
    assert drop_most_cited([A, B, C], "X [3]. Y [1].") == [A, B]


def test_drop_most_cited_ignores_numbers_with_no_passage() -> None:
    assert drop_most_cited([A, B], "X [7][7]. Y [2].") == [A]


def test_drop_most_cited_is_none_when_the_answer_cites_nothing() -> None:
    assert drop_most_cited([A, B], "No citations here.") is None


def test_add_distractor_puts_it_first_where_it_is_hardest_to_ignore() -> None:
    distractor = hit("unrelated")

    assert add_distractor([A, B], distractor) == [distractor, A, B]
