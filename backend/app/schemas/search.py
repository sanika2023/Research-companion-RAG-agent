import uuid
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class SearchRequest(BaseModel):
    query: Query
    top_k: int | None = Field(default=None, ge=1, le=50)  # None = server default


class SearchHitOut(BaseModel):
    chunk_id: uuid.UUID
    doc_id: uuid.UUID
    page: int
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    bbox: list[list[float]]
    score: float
    keyword_rank: int | None
    vector_rank: int | None


class SearchResponse(BaseModel):
    doc_id: uuid.UUID
    query: str
    hits: list[SearchHitOut]
