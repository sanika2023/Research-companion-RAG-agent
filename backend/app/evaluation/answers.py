"""Saved answer-run results and what is left to run, so a stopped run can resume."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from app.evaluation.queries import Query
from app.schemas.ask import AskResponse
from app.schemas.diagnose import DiagnoseResponse

ANSWERS_PATH = Path("../eval/results/answers.jsonl")


class Check(BaseModel):
    report: DiagnoseResponse
    seconds: float


class AnswerRecord(BaseModel):
    id: str
    answer: AskResponse | None  # None until /ask succeeds
    ask_seconds: float | None
    checks: list[Check] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)  # kept so failures can be reported


@dataclass(frozen=True)
class Step:
    query: Query
    ask: bool
    checks: int  # still to run; the runner skips them if the new answer is not checkable


def checkable(answer: AskResponse) -> bool:
    """Same rule as the UI's "Check this answer" button."""
    return not answer.refused and bool(answer.passage_ids)


def plan(
    queries: Sequence[Query], *, records: Mapping[str, AnswerRecord], checks: int
) -> list[Step]:
    steps = []
    for query in queries:
        record = records.get(query.id)
        if record is None or record.answer is None:
            steps.append(Step(query, ask=True, checks=checks))
        elif checkable(record.answer) and len(record.checks) < checks:
            steps.append(Step(query, ask=False, checks=checks - len(record.checks)))
    return steps


def load_records(path: Path = ANSWERS_PATH) -> dict[str, AnswerRecord]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (AnswerRecord.model_validate_json(line) for line in lines if line.strip())
    return {r.id: r for r in records}


def save_records(path: Path, records: Mapping[str, AnswerRecord]) -> None:
    # Write then rename, so stopping mid-save can't corrupt earlier results.
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(r.model_dump_json() + "\n" for r in records.values()), "utf-8")
    tmp.replace(path)
