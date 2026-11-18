"""Controlled changes to an answer's inputs; each changes one thing, so effects are attributable."""

from collections import Counter

from app.agent.nodes.check_citations import CITATION_MARKER
from app.retrieval.hybrid import SearchHit


def reorder(passages: list[SearchHit]) -> list[SearchHit]:
    return passages[::-1]


def drop_most_cited(passages: list[SearchHit], answer: str) -> list[SearchHit] | None:
    """Remove the answer's main evidence; None when the answer cites no passage."""
    counts: Counter[int] = Counter()
    for match in CITATION_MARKER.finditer(answer):
        counts.update(int(n) for n in match.group(2).split(","))
    valid = {n: c for n, c in counts.items() if 1 <= n <= len(passages)}
    if not valid:
        return None
    # Counter keeps first-seen order, and max() returns the first of equal counts.
    number = max(valid, key=lambda n: valid[n])
    return passages[: number - 1] + passages[number:]


def add_distractor(passages: list[SearchHit], distractor: SearchHit) -> list[SearchHit]:
    return [distractor, *passages]
