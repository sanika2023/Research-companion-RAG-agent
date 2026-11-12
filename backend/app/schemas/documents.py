import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentUploaded(BaseModel):
    doc_id: uuid.UUID
    filename: str
    page_count: int
    chunk_count: int


class DocumentSummary(BaseModel):
    doc_id: uuid.UUID
    filename: str
    page_count: int
    chunk_count: int
    created_at: datetime
