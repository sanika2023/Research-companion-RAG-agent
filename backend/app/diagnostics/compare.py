"""How much a perturbed answer agrees with the original."""

import math
from typing import Literal

from app.agent.nodes.check_citations import CITATION_MARKER

Verdict = Literal["agrees", "contradicts", "missing"]


def strip_citations(text: str) -> str:
    # Perturbations renumber passages, so [n] markers differ even when the content doesn't.
    return CITATION_MARKER.sub("", text).strip()


def cosine(a: list[float], b: list[float]) -> float:
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0.0


def rescale(similarity: float, *, floor: float) -> float:
    """Map [floor, 1] to [0, 1]: any two answers on one topic embed at least ~floor apart."""
    return min(1.0, max(0.0, (similarity - floor) / (1 - floor)))


def claim_agreement(verdicts: list[Verdict]) -> float | None:
    return verdicts.count("agrees") / len(verdicts) if verdicts else None
