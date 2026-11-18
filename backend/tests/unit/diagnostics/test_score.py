import pytest

from app.diagnostics.score import Perturbation, agreement, risk, uncertainty

EQUAL: dict[Perturbation, float] = {
    "paraphrase": 1.0,
    "reorder": 1.0,
    "distractor": 1.0,
    "drop_cited": 0.0,
}


def test_agreement_averages_the_available_signals() -> None:
    assert agreement(similarity=0.8, claim_agreement=0.4) == pytest.approx(0.6)


def test_agreement_uses_one_signal_when_the_other_is_missing() -> None:
    assert agreement(similarity=None, claim_agreement=0.4) == 0.4


def test_agreement_is_none_without_any_signal() -> None:
    assert agreement(similarity=None, claim_agreement=None) is None


def test_risk_is_disagreement_for_perturbations_that_should_not_change_the_answer() -> None:
    assert risk("paraphrase", 0.9) == pytest.approx(0.1)


def test_risk_of_drop_cited_is_agreement_since_the_answer_should_change() -> None:
    # Same answer without its main evidence suggests it never depended on that evidence.
    assert risk("drop_cited", 0.9) == pytest.approx(0.9)


def test_uncertainty_is_the_weighted_mean_of_the_risks() -> None:
    risks: dict[Perturbation, float | None] = {
        "paraphrase": 0.2,
        "reorder": 0.4,
        "distractor": 0.0,
        "drop_cited": 1.0,
    }

    assert uncertainty(risks, EQUAL) == pytest.approx(0.2)  # drop_cited has weight 0


def test_uncertainty_skips_signals_that_could_not_be_measured() -> None:
    risks: dict[Perturbation, float | None] = {
        "paraphrase": 0.2,
        "reorder": None,
        "distractor": 0.4,
        "drop_cited": None,
    }

    assert uncertainty(risks, EQUAL) == pytest.approx(0.3)


def test_uncertainty_is_none_when_nothing_weighted_was_measured() -> None:
    risks: dict[Perturbation, float | None] = {
        "paraphrase": None,
        "reorder": None,
        "distractor": None,
        "drop_cited": 0.5,
    }

    assert uncertainty(risks, EQUAL) is None
