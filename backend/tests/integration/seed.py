import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.models import Chunk, Document
from tests.conftest import FakeEmbedder


@dataclass(frozen=True)
class SeededPaper:
    doc_id: uuid.UUID
    chunk_ids: list[uuid.UUID]  # same order as the texts passed in


async def seed_paper(
    engine: AsyncEngine,
    texts: list[str],
    filename: str = "p.pdf",
    vectors: list[list[float]] | None = None,
) -> SeededPaper:
    """Store one paper, one chunk per page; embeddings default to the FakeEmbedder's."""
    vectors = vectors or await FakeEmbedder().embed(texts)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        doc = Document(filename=filename, page_count=len(texts))
        doc.chunks = [
            Chunk(
                page=i + 1,
                chunk_index=i,
                text=t,
                char_start=0,
                char_end=len(t),
                bbox=[[0.0, 0.0, 1.0, 1.0]],
                embedding=v,
            )
            for i, (t, v) in enumerate(zip(texts, vectors, strict=True))
        ]
        session.add(doc)
        await session.commit()
        return SeededPaper(doc.id, [c.id for c in doc.chunks])
