import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.ask import Question

Answer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)]


class DiagnoseRequest(BaseModel):
    """An answer from /ask, sent back to be stress-tested."""

    question: Question
    answer: Answer
    passage_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)  # from the /ask response
    sub_questions: list[str] = Field(default_factory=list, max_length=10)


class SignalOut(BaseModel):
    kind: Literal["paraphrase", "reorder", "distractor", "drop_cited"]
    status: Literal["ok", "skipped", "failed"]
    weight: float  # its share of the overall score; 0 = shown but not scored
    risk: float | None  # 0 = answer behaved as it should, 1 = it did not
    similarity: float | None  # rescaled embedding similarity to the original answer
    claim_agreement: float | None  # fraction of the original's claims this answer agrees with
    contradictions: int | None
    question: str | None  # the question asked in this run
    answer: str | None  # the perturbed answer, for auditing
    refused: bool


class DiagnoseResponse(BaseModel):
    doc_id: uuid.UUID
    uncertainty: float | None  # 0-1; None when no scored perturbation could be measured
    signals: list[SignalOut]
    claims: list[str]  # the original answer split into claims, as judged
    flags: list[str]  # e.g. "judge_failed"
