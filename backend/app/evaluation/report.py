"""Markdown tables for the thesis report."""

from collections.abc import Mapping, Sequence

from app.evaluation.metrics import Rank, hit_rate, mean_reciprocal_rank


def retrieval_table(ranks: Mapping[str, Sequence[Rank]], *, ks: Sequence[int]) -> str:
    header = ["Method", *(f"Hit@{k}" for k in ks), "MRR"]
    rows = [
        [method, *(f"{hit_rate(r, k=k):.2f}" for k in ks), f"{mean_reciprocal_rank(r):.2f}"]
        for method, r in ranks.items()
    ]
    return table(header, rows)


def table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = [header, ["---"] * len(header), *rows]
    return "\n".join("| " + " | ".join(cells) + " |" for cells in lines)
