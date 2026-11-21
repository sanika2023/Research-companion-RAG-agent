import pytest

from app.evaluation.metrics import (
    RefusalCounts,
    auroc,
    first_hit_rank,
    hit_rate,
    mean_reciprocal_rank,
    refusal_counts,
    spread,
)


def test_first_hit_rank_is_the_one_based_position_of_the_first_expected_page() -> None:
    assert first_hit_rank([4, 7, 5, 5], expected={5}) == 3


def test_first_hit_rank_accepts_any_of_several_expected_pages() -> None:
    assert first_hit_rank([9, 3, 2], expected={2, 3}) == 2


def test_first_hit_rank_is_none_when_no_expected_page_is_retrieved() -> None:
    assert first_hit_rank([1, 2], expected={5}) is None


def test_hit_rate_counts_ranks_within_k() -> None:
    assert hit_rate([1, 3, None, 6], k=3) == 0.5


def test_hit_rate_of_no_questions_is_zero() -> None:
    assert hit_rate([], k=5) == 0.0


def test_mean_reciprocal_rank_scores_misses_as_zero() -> None:
    assert mean_reciprocal_rank([1, 2, None, 4]) == pytest.approx((1 + 0.5 + 0 + 0.25) / 4)


def test_auroc_is_one_when_every_wrong_answer_has_higher_risk() -> None:
    assert auroc(wrong=[0.5, 0.4], right=[0.1, 0.2]) == 1.0


def test_auroc_is_zero_when_the_ordering_is_reversed() -> None:
    assert auroc(wrong=[0.1], right=[0.3, 0.4]) == 0.0


def test_auroc_counts_ties_as_half() -> None:
    # Pairs: (0.3 vs 0.3) tie = 0.5, (0.3 vs 0.1) win = 1 -> 1.5 / 2
    assert auroc(wrong=[0.3], right=[0.3, 0.1]) == 0.75


def test_auroc_is_undefined_without_both_groups() -> None:
    assert auroc(wrong=[], right=[0.1]) is None


def test_refusal_counts_split_answerable_and_unanswerable_questions() -> None:
    # (answerable, refused)
    results = [(False, True), (False, False), (True, True), (True, False), (True, False)]

    assert refusal_counts(results) == RefusalCounts(
        correct_refusals=1, missed_refusals=1, false_refusals=1, answered=2
    )


def test_spread_reports_mean_standard_deviation_and_range() -> None:
    summary = spread([0.1, 0.2, 0.3])

    assert summary.mean == pytest.approx(0.2)
    assert summary.std == pytest.approx(0.1)  # sample standard deviation
    assert (summary.low, summary.high) == (0.1, 0.3)


def test_spread_of_one_value_has_no_deviation() -> None:
    assert spread([0.4]).std == 0.0
