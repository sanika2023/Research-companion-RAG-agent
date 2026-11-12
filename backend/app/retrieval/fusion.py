from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T", bound=Hashable)


@dataclass(frozen=True)
class Fused(Generic[T]):
    id: T
    score: float
    ranks: tuple[int | None, ...]  # 1-based rank in each input list; None if absent


def reciprocal_rank_fusion(rankings: Sequence[Sequence[T]], k: int) -> list[Fused[T]]:
    """Merge ranked lists by summing 1/(k + rank).

    Uses ranks only, so lists with incomparable scores (ts_rank vs. cosine) can be combined.
    Larger k flattens the curve, favouring items that several lists agree on.
    """
    ranks: dict[T, list[int | None]] = {}  # insertion order = first-seen, keeps ties stable
    for list_index, ranking in enumerate(rankings):
        for rank, item in enumerate(ranking, start=1):
            ranks.setdefault(item, [None] * len(rankings))[list_index] = rank

    fused = [
        Fused(item, sum(1 / (k + r) for r in item_ranks if r is not None), tuple(item_ranks))
        for item, item_ranks in ranks.items()
    ]
    return sorted(fused, key=lambda f: f.score, reverse=True)  # stable sort
