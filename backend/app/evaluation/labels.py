"""The hand-labelling sheet: each answer beside its reference, with columns to fill in.

Run from backend/ (safe to rerun; filled-in labels are kept):
    uv run python -m app.evaluation.labels
"""

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.evaluation.answers import AnswerRecord, load_records
from app.evaluation.queries import Query, load_queries

LABELS_PATH = Path("../eval/results/labels.csv")
LABEL_FIELDS = ("correctness", "citations_support", "notes")  # filled in by hand
# The risk score is left out on purpose: seeing it while labelling would bias the labels.
FIELDS = (
    "id",
    "paper",
    "type",
    "answerable",
    "question",
    "reference",
    "answer",
    "refused",
    "cited_passages",
    *LABEL_FIELDS,
)
CHANGED = "answer changed since labelled; please re-check"

Row = dict[str, str]


def label_rows(
    queries: Sequence[Query], records: Mapping[str, AnswerRecord], *, existing: Mapping[str, Row]
) -> list[Row]:
    rows = []
    for query in queries:
        record = records.get(query.id)
        if record is None or record.answer is None:
            continue
        answer = record.answer
        row: Row = {
            "id": query.id,
            "paper": query.paper,
            "type": query.type,
            "answerable": "yes" if query.answerable else "no",
            "question": query.question,
            "reference": query.reference,
            "answer": answer.answer,
            "refused": "yes" if answer.refused else "no",
            "cited_passages": "\n\n".join(
                f"[{c.number}] p{c.page}: {c.text}" for c in answer.citations
            ),
        }
        old = existing.get(query.id, {})
        row |= {field: old.get(field, "") for field in LABEL_FIELDS}
        if old.get("answer") not in (None, answer.answer) and CHANGED not in row["notes"]:
            row["notes"] = f"{row['notes']} ({CHANGED})".strip()
        rows.append(row)
    return rows


def read_labels(path: Path = LABELS_PATH) -> dict[str, Row]:
    if not path.exists():
        return {}
    # utf-8-sig: Excel adds a byte-order mark when it saves a CSV.
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def write_labels(path: Path, rows: Sequence[Row]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = label_rows(load_queries(), load_records(), existing=read_labels())
    write_labels(LABELS_PATH, rows)
    print(f"{len(rows)} answers in {LABELS_PATH}")


if __name__ == "__main__":
    main()
