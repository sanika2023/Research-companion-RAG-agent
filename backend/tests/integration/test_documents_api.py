import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import Engine, text

from app.api.deps import get_ingest_settings
from app.core.config import IngestSettings
from app.main import app
from tests.pdf_factory import Text, make_pdf

pytestmark = pytest.mark.integration

PDF = make_pdf([[Text(72, 72, "Attention is all you need.")], [Text(72, 72, "Page two.")]])


def disable_uploads() -> None:
    """The public demo's setting; the client fixture clears overrides afterwards."""
    app.dependency_overrides[get_ingest_settings] = lambda: IngestSettings(
        chunk_size=1000, chunk_overlap=150, max_upload_mb=1, allow_uploads=False
    )


async def upload(client: AsyncClient, data: bytes, name: str = "paper.pdf") -> Response:
    return await client.post("/documents", files={"file": (name, data, "application/pdf")})


async def test_upload_returns_document_summary(client: AsyncClient) -> None:
    response = await upload(client, PDF)

    assert response.status_code == 201
    body = response.json()
    assert (body["filename"], body["page_count"], body["chunk_count"]) == ("paper.pdf", 2, 2)
    assert body["doc_id"]


async def test_uploaded_documents_are_listed_newest_first(client: AsyncClient) -> None:
    await upload(client, PDF, "first.pdf")
    await upload(client, PDF, "second.pdf")

    response = await client.get("/documents")

    assert response.status_code == 200
    assert [(d["filename"], d["chunk_count"]) for d in response.json()] == [
        ("second.pdf", 2),
        ("first.pdf", 2),
    ]


async def test_upload_keeps_only_the_base_filename(client: AsyncClient) -> None:
    response = await upload(client, PDF, "../../etc/paper.pdf")

    assert response.json()["filename"] == "paper.pdf"


async def test_non_pdf_upload_is_a_400(client: AsyncClient) -> None:
    response = await upload(client, b"hello, I am a text file", "notes.pdf")

    assert response.status_code == 400
    assert (await client.get("/documents")).json() == []


async def test_pdf_without_text_is_a_400(client: AsyncClient) -> None:
    response = await upload(client, make_pdf([[]]))

    assert response.status_code == 400
    assert "no extractable text" in response.json()["detail"]


async def test_upload_over_the_size_limit_is_a_413(client: AsyncClient) -> None:
    response = await upload(client, b"%PDF-" + b"0" * (1024 * 1024))

    assert response.status_code == 413
    assert (await client.get("/documents")).json() == []


async def test_uploaded_pdf_is_served_back_for_the_viewer(client: AsyncClient) -> None:
    doc_id = (await upload(client, PDF, "paper.pdf")).json()["doc_id"]

    response = await client.get(f"/documents/{doc_id}/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == PDF
    assert response.headers["content-disposition"].startswith("inline")


async def test_file_of_unknown_paper_is_a_404(client: AsyncClient) -> None:
    response = await client.get(f"/documents/{uuid.uuid4()}/file")

    assert response.status_code == 404


async def test_paper_without_a_stored_pdf_is_a_404(
    client: AsyncClient, sync_engine: Engine
) -> None:
    # e.g. a paper uploaded before PDFs moved into the database whose file was already gone
    doc_id = (await upload(client, PDF)).json()["doc_id"]
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM document_files WHERE doc_id = :d"), {"d": doc_id})

    response = await client.get(f"/documents/{doc_id}/file")

    assert response.status_code == 404


async def test_features_report_that_uploads_are_enabled(client: AsyncClient) -> None:
    response = await client.get("/features")

    assert response.json() == {"uploads_enabled": True}


async def test_upload_is_a_403_when_uploads_are_disabled(client: AsyncClient) -> None:
    disable_uploads()

    response = await upload(client, PDF)

    assert response.status_code == 403
    assert (await client.get("/documents")).json() == []


async def test_features_report_that_uploads_are_disabled(client: AsyncClient) -> None:
    disable_uploads()

    response = await client.get("/features")

    assert response.json() == {"uploads_enabled": False}
