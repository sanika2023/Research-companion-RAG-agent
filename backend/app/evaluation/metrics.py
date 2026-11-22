"""Pure metric functions for the evaluation scripts in `eval/`."""

import statistics
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass

Rank = int | None  # 1-based position of the first relevant result; None = not retrieved


def first_hit_rank(pages: Sequence[int], *, expected: Collection[int]) -> Rank:
    """Position of the first retrieved passage on an expected page."""
    return next((i for i, page in enumerate(pages, start=1) if page in expected), None)


def hit_rate(ranks: Sequence[Rank], *, k: int) -> float:
    if not ranks:
        return 0.0
    return sum(r is not None and r <= k for r in ranks) / len(ranks)


def mean_reciprocal_rank(ranks: Sequence[Rank]) -> float:
    if not ranks:
        return 0.0
    return sum(1 / r for r in ranks if r is not None) / len(ranks)


def auroc(*, wrong: Sequence[float], right: Sequence[float]) -> float | None:
    """Chance a wrong answer has a higher risk score than a right one (ties count half)."""
    if not wrong or not right:
        return None
    # Pairwise (Mann-Whitney) form: exact and fine for a few dozen answers.
    wins = sum(1.0 if w > r else 0.5 if w == r else 0.0 for w in wrong for r in right)
    return wins / (len(wrong) * len(right))


@dataclass(frozen=True)
class RefusalCounts:
    correct_refusals: int  # unanswerable and refused
    missed_refusals: int  # unanswerable but answered
    false_refusals: int  # answerable but refused
    answered: int  # answerable and answered


def refusal_counts(results: Iterable[tuple[bool, bool]]) -> RefusalCounts:
    """Tally (answerable, refused) pairs."""
    counts = {(a, r): 0 for a in (True, False) for r in (True, False)}
    for answerable, refused in results:
        counts[answerable, refused] += 1
    return RefusalCounts(
        correct_refusals=counts[False, True],
        missed_refusals=counts[False, False],
        false_refusals=counts[True, True],
        answered=counts[True, False],
    )


@dataclass(frozen=True)
class Spread:
    mean: float
    std: float
    low: float
    high: float


def spread(values: Sequence[float]) -> Spread:
    """Summary of repeated scores for the same answer."""
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return Spread(statistics.fmean(values), std, min(values), max(values))
