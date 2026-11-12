from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.api.deps import get_embedder, get_ingest_settings
from app.core.config import IngestSettings
from app.db.session import get_session
from app.main import app
from tests.conftest import FakeEmbedder
from tests.pdf_factory import Text, make_pdf

pytestmark = pytest.mark.integration

PDF = make_pdf([[Text(72, 72, "Attention is all you need.")], [Text(72, 72, "Page two.")]])


@pytest.fixture
async def client(
    sync_engine: Engine, async_engine: AsyncEngine, tmp_path: Path
) -> AsyncIterator[AsyncClient]:
    async def test_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(async_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_ingest_settings] = lambda: IngestSettings(
        chunk_size=1000, chunk_overlap=150, max_upload_mb=1, upload_dir=tmp_path
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


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
