from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.models import Chunk, Document
from app.ingestion.parse import InvalidPDFError
from app.ingestion.pipeline import IngestResult, NoTextError, ingest_pdf
from tests.conftest import FakeEmbedder
from tests.pdf_factory import Text, make_pdf

pytestmark = pytest.mark.integration

TWO_PAGE_PDF = make_pdf(
    [[Text(72, 72, "Transformers rely on attention.")], [Text(72, 72, "Hallucination is common.")]]
)


async def ingest(engine: AsyncEngine, data: bytes, upload_dir: Path) -> IngestResult:
    async with AsyncSession(engine) as session:
        return await ingest_pdf(
            data,
            "paper.pdf",
            session=session,
            embedder=FakeEmbedder(),
            upload_dir=upload_dir,
            chunk_size=1000,
            chunk_overlap=150,
        )


async def count(engine: AsyncEngine, model: type[Document] | type[Chunk]) -> int:
    async with AsyncSession(engine) as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_ingest_stores_document_and_page_tagged_chunks(
    sync_engine: Engine, async_engine: AsyncEngine, tmp_path: Path
) -> None:
    result = await ingest(async_engine, TWO_PAGE_PDF, tmp_path)

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
    sync_engine: Engine, async_engine: AsyncEngine, tmp_path: Path
) -> None:
    await ingest(async_engine, TWO_PAGE_PDF, tmp_path)
    [expected] = await FakeEmbedder().embed(["Transformers rely on attention."])

    async with AsyncSession(async_engine) as session:
        chunk = (await session.execute(select(Chunk).where(Chunk.page == 1))).scalar_one()

    assert list(chunk.embedding) == pytest.approx(expected, abs=1e-6)


async def test_ingested_chunks_are_keyword_searchable(
    sync_engine: Engine, async_engine: AsyncEngine, tmp_path: Path
) -> None:
    await ingest(async_engine, TWO_PAGE_PDF, tmp_path)

    with sync_engine.connect() as conn:
        pages = (
            conn.execute(
                text("SELECT page FROM chunks WHERE tsv @@ plainto_tsquery('english', 'attention')")
            )
            .scalars()
            .all()
        )

    assert pages == [1]


async def test_ingest_saves_the_original_pdf_under_its_document_id(
    sync_engine: Engine, async_engine: AsyncEngine, tmp_path: Path
) -> None:
    result = await ingest(async_engine, TWO_PAGE_PDF, tmp_path)

    saved = tmp_path / f"{result.doc_id}.pdf"
    assert saved.read_bytes() == TWO_PAGE_PDF


async def test_invalid_pdf_is_rejected_and_nothing_is_stored(
    sync_engine: Engine, async_engine: AsyncEngine, tmp_path: Path
) -> None:
    with pytest.raises(InvalidPDFError):
        await ingest(async_engine, b"not a pdf", tmp_path)

    assert await count(async_engine, Document) == 0
    assert list(tmp_path.iterdir()) == []


async def test_pdf_without_extractable_text_is_rejected(
    sync_engine: Engine, async_engine: AsyncEngine, tmp_path: Path
) -> None:
    with pytest.raises(NoTextError):
        await ingest(async_engine, make_pdf([[], []]), tmp_path)

    assert await count(async_engine, Document) == 0


async def test_failure_while_saving_the_file_rolls_back_the_database(
    sync_engine: Engine, async_engine: AsyncEngine, tmp_path: Path
) -> None:
    not_a_dir = tmp_path / "blocker"
    not_a_dir.write_text("a file where the upload directory should be")

    with pytest.raises(OSError):
        await ingest(async_engine, TWO_PAGE_PDF, not_a_dir)

    assert await count(async_engine, Document) == 0
    assert await count(async_engine, Chunk) == 0
