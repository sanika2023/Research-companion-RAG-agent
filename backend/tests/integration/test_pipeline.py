import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.models import Chunk, Document
from app.ingestion.parse import InvalidPDFError
from app.ingestion.pipeline import IngestResult, NoTextError, ingest_pdf
from app.ingestion.store import get_pdf
from tests.conftest import FakeEmbedder
from tests.pdf_factory import Text, make_pdf

pytestmark = pytest.mark.integration

TWO_PAGE_PDF = make_pdf(
    [[Text(72, 72, "Transformers rely on attention.")], [Text(72, 72, "Hallucination is common.")]]
)


async def ingest(engine: AsyncEngine, data: bytes) -> IngestResult:
    async with AsyncSession(engine) as session:
        return await ingest_pdf(
            data,
            "paper.pdf",
            session=session,
            embedder=FakeEmbedder(),
            chunk_size=1000,
            chunk_overlap=150,
        )


async def count(engine: AsyncEngine, model: type[Document] | type[Chunk]) -> int:
    async with AsyncSession(engine) as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_ingest_stores_document_and_page_tagged_chunks(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    result = await ingest(async_engine, TWO_PAGE_PDF)

    async with AsyncSession(async_engine) as session:
        doc = (await session.execute(select(Document))).scalar_one()
        chunks = (await session.execute(select(Chunk).order_by(Chunk.chunk_index))).scalars().all()

    assert (doc.id, doc.filename, doc.page_count) == (result.doc_id, "paper.pdf", 2)
    assert [(c.page, c.text) for c in chunks] == [
        (1, "Transformers rely on attention."),
        (2, "Hallucination is common."),
    ]
    assert result.chunk_count == 2


async def test_ingest_stores_each_chunks_embedding(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    await ingest(async_engine, TWO_PAGE_PDF)
    [expected] = await FakeEmbedder().embed(["Transformers rely on attention."])

    async with AsyncSession(async_engine) as session:
        chunk = (await session.execute(select(Chunk).where(Chunk.page == 1))).scalar_one()

    assert list(chunk.embedding) == pytest.approx(expected, abs=1e-6)


async def test_ingested_chunks_are_keyword_searchable(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    await ingest(async_engine, TWO_PAGE_PDF)

    with sync_engine.connect() as conn:
        pages = (
            conn.execute(
                text("SELECT page FROM chunks WHERE tsv @@ plainto_tsquery('english', 'attention')")
            )
            .scalars()
            .all()
        )

    assert pages == [1]


async def test_ingest_stores_the_original_pdf_with_the_document(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    result = await ingest(async_engine, TWO_PAGE_PDF)

    async with AsyncSession(async_engine) as session:
        assert await get_pdf(session, result.doc_id) == TWO_PAGE_PDF


async def test_invalid_pdf_is_rejected_and_nothing_is_stored(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    with pytest.raises(InvalidPDFError):
        await ingest(async_engine, b"not a pdf")

    assert await count(async_engine, Document) == 0


async def test_pdf_without_extractable_text_is_rejected(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    with pytest.raises(NoTextError):
        await ingest(async_engine, make_pdf([[], []]))

    assert await count(async_engine, Document) == 0
