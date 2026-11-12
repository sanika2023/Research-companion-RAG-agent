import pytest

from app.retrieval.fusion import reciprocal_rank_fusion


def test_item_ranked_by_both_lists_beats_items_ranked_by_one() -> None:
    fused = reciprocal_rank_fusion([["a", "both"], ["b", "both"]], k=60)

    assert fused[0].id == "both"


def test_score_is_sum_of_reciprocal_ranks() -> None:
    [only] = reciprocal_rank_fusion([["x"], ["x"]], k=60)

    assert only.score == pytest.approx(1 / 61 + 1 / 61)


def test_ranks_from_each_list_are_kept_for_auditing() -> None:
    fused = {f.id: f for f in reciprocal_rank_fusion([["a", "b"], ["b"]], k=60)}

    assert fused["a"].ranks == (1, None)
    assert fused["b"].ranks == (2, 1)


def test_ties_keep_first_list_order() -> None:
    # "a" and "b" each appear once at rank 1; the order must be deterministic.
    fused = reciprocal_rank_fusion([["a"], ["b"]], k=60)

    assert [f.id for f in fused] == ["a", "b"]


def test_empty_lists_fuse_to_nothing() -> None:
    assert reciprocal_rank_fusion([[], []], k=60) == []


def test_smaller_k_rewards_top_ranks_more() -> None:
    # "top" is 1st in one list; "mid" is 4th in both.
    lists = [["top", "x", "w", "mid"], ["y", "z", "v", "mid"]]

    def order(k: int) -> list[str]:
        return [f.id for f in reciprocal_rank_fusion(lists, k=k)]

    assert order(1).index("top") < order(1).index("mid")  # 1/2 > 2/5
    assert order(60).index("mid") < order(60).index("top")  # 2/64 > 1/61
