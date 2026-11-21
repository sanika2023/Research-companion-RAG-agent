from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, model_validator

QueryType = Literal["fact", "number", "multi_step", "formula", "unanswerable"]

# Default location, relative to backend/ (where the scripts are run from).
QUERIES_PATH = Path("../eval/queries/queries.jsonl")


class Query(BaseModel):
    id: str
    paper: str  # filename as uploaded; ids change if a paper is re-ingested
    type: QueryType
    answerable: bool
    question: str  # phrased like a user who has only skimmed the paper
    # The same question in the paper's own terms, to measure how wording affects retrieval.
    paper_wording: str | None = None
    expected_pages: list[int]
    reference: str

    @model_validator(mode="after")
    def _answerable_needs_pages(self) -> Self:
        if self.answerable and not self.expected_pages:
            raise ValueError(f"{self.id}: answerable queries need expected_pages")
        return self


def load_queries(path: Path = QUERIES_PATH) -> list[Query]:
    """Read the JSON-lines question set."""
    lines = path.read_text(encoding="utf-8").splitlines()
    queries = [Query.model_validate_json(line) for line in lines if line.strip()]
    seen: set[str] = set()
    for query in queries:
        if query.id in seen:
            raise ValueError(f"duplicate query id: {query.id}")
        seen.add(query.id)
    return queries
