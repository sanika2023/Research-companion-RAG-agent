"""Turn per-perturbation agreement into a 0-1 uncertainty score."""

from collections.abc import Mapping
from typing import Literal

Perturbation = Literal["paraphrase", "reorder", "distractor", "drop_cited"]


def agreement(*, similarity: float | None, claim_agreement: float | None) -> float | None:
    signals = [s for s in (similarity, claim_agreement) if s is not None]
    return sum(signals) / len(signals) if signals else None


def risk(kind: Perturbation, agreement: float) -> float:
    # Dropping the main evidence *should* change the answer; the others should not.
    return agreement if kind == "drop_cited" else 1 - agreement


def uncertainty(
    risks: Mapping[Perturbation, float | None], weights: Mapping[Perturbation, float]
) -> float | None:
    measured = [(r, weights[k]) for k, r in risks.items() if r is not None and weights[k] > 0]
    total = sum(w for _, w in measured)
    return sum(r * w for r, w in measured) / total if total else None
