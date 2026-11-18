import uuid
from typing import Annotated

from pydantic import BaseModel, StringConstraints

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class AskRequest(BaseModel):
    question: Question


class CitationOut(BaseModel):
    number: int  # matches the [n] marker in the answer text
    chunk_id: uuid.UUID
    page: int
    text: str
    bbox: list[list[float]]


class AskResponse(BaseModel):
    doc_id: uuid.UUID
    question: str
    answer: str
    citations: list[CitationOut]
    refused: bool
    sub_questions: list[str]
    flags: list[str]  # e.g. "uncited", "invalid_citations_removed"
    # Every passage shown to the model, in prompt order; lets /diagnose re-run the answer.
    passage_ids: list[uuid.UUID]
