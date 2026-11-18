import math

import pytest

from app.diagnostics.compare import claim_agreement, cosine, rescale, strip_citations


def test_strip_citations_removes_markers_so_renumbered_answers_compare_equal() -> None:
    assert strip_citations("MetaQA uses MRs [1, 2]. It works [3].") == "MetaQA uses MRs. It works."


def test_cosine_of_identical_vectors_is_one() -> None:
    assert cosine([0.6, 0.8], [0.6, 0.8]) == pytest.approx(1.0)


def test_cosine_of_orthogonal_vectors_is_zero() -> None:
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_does_not_assume_unit_vectors() -> None:
    assert cosine([3.0, 0.0], [5.0, 0.0]) == pytest.approx(1.0)


def test_cosine_with_a_zero_vector_is_zero_not_a_crash() -> None:
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_rescale_maps_the_floor_to_zero_and_one_to_one() -> None:
    assert rescale(0.7, floor=0.7) == pytest.approx(0.0)
    assert rescale(0.85, floor=0.7) == pytest.approx(0.5)
    assert rescale(1.0, floor=0.7) == pytest.approx(1.0)


def test_rescale_clamps_below_the_floor_to_zero() -> None:
    assert rescale(0.2, floor=0.7) == 0.0


def test_claim_agreement_is_the_fraction_of_claims_that_agree() -> None:
    assert claim_agreement(["agrees", "contradicts", "missing", "agrees"]) == 0.5


def test_claim_agreement_is_none_without_claims() -> None:
    assert claim_agreement([]) is None


def test_claim_agreement_is_finite_for_a_single_claim() -> None:
    assert math.isclose(claim_agreement(["agrees"]) or 0.0, 1.0)
