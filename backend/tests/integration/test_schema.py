from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.models import Chunk, Document
from tests.integration.conftest import alembic_config

pytestmark = pytest.mark.integration

VECTOR_384 = "[" + ",".join(["0.1"] * 384) + "]"


def _insert_doc_with_chunk(engine: Engine, chunk_text: str) -> None:
    with engine.begin() as conn:
        doc_id = conn.execute(
            text("INSERT INTO documents (filename, page_count) VALUES ('a.pdf', 1) RETURNING id")
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO chunks (doc_id, page, chunk_index, text, char_start, char_end,"
                " bbox, embedding) VALUES (:d, 1, 0, :t, 0, 10, '[]', :e)"
            ),
            {"d": doc_id, "t": chunk_text, "e": VECTOR_384},
        )


def test_migration_creates_documents_and_chunks_tables(sync_engine: Engine) -> None:
    assert {"documents", "chunks"} <= set(inspect(sync_engine).get_table_names())


def test_migration_creates_keyword_and_vector_indexes(sync_engine: Engine) -> None:
    index_defs = {i["name"]: i for i in inspect(sync_engine).get_indexes("chunks")}

    assert index_defs["ix_chunks_tsv"]["dialect_options"]["postgresql_using"] == "gin"
    assert index_defs["ix_chunks_embedding_hnsw"]["dialect_options"]["postgresql_using"] == "hnsw"


def test_chunk_tsvector_is_generated_from_text(sync_engine: Engine) -> None:
    _insert_doc_with_chunk(sync_engine, "Transformers use self-attention")

    with sync_engine.connect() as conn:
        hits = conn.execute(
            text("SELECT count(*) FROM chunks WHERE tsv @@ plainto_tsquery('english', 'attention')")
        ).scalar_one()

    assert hits == 1


def test_deleting_a_document_deletes_its_chunks(sync_engine: Engine) -> None:
    _insert_doc_with_chunk(sync_engine, "some text")

    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM documents"))
        remaining = conn.execute(text("SELECT count(*) FROM chunks")).scalar_one()

    assert remaining == 0


async def test_orm_roundtrips_chunk_with_embedding_and_provenance(
    sync_engine: Engine, async_engine: AsyncEngine
) -> None:
    embedding = [0.5] * 384
    async with AsyncSession(async_engine) as session:
        doc = Document(filename="paper.pdf", page_count=3)
        doc.chunks.append(
            Chunk(
                page=2,
                chunk_index=0,
                text="hello",
                char_start=5,
                char_end=10,
                bbox=[[1.0, 2.0, 3.0, 4.0]],
                embedding=embedding,
            )
        )
        session.add(doc)
        await session.commit()

        chunk = (await session.execute(select(Chunk))).scalar_one()

    assert chunk.page == 2
    assert chunk.bbox == [[1.0, 2.0, 3.0, 4.0]]
    assert list(chunk.embedding) == pytest.approx(embedding)


def test_migration_moves_pdfs_saved_on_disk_into_the_database(
    migrated_db_url: str,
    sync_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = alembic_config(migrated_db_url)
    command.downgrade(config, "0001")  # back to when PDFs lived in UPLOAD_DIR
    try:
        with sync_engine.begin() as conn:
            insert = text(
                "INSERT INTO documents (filename, page_count) VALUES (:f, 1) RETURNING id"
            )
            saved = conn.execute(insert, {"f": "saved.pdf"}).scalar_one()
            lost = conn.execute(insert, {"f": "lost.pdf"}).scalar_one()
        (tmp_path / f"{saved}.pdf").write_bytes(b"%PDF-saved")
        monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

        command.upgrade(config, "head")
    finally:
        command.upgrade(config, "head")  # leave the shared test database migrated

    with sync_engine.connect() as conn:
        rows = conn.execute(text("SELECT doc_id, data FROM document_files")).all()
    assert [(doc_id, bytes(data)) for doc_id, data in rows] == [(saved, b"%PDF-saved")]
    assert lost not in {doc_id for doc_id, _ in rows}
