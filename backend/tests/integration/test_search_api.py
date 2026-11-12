import uuid

import pytest
from httpx import AsyncClient

from tests.pdf_factory import Text, make_pdf

pytestmark = pytest.mark.integration

PAPER = make_pdf(
    [
        [Text(72, 72, "Metamorphic relations expose hallucinations.")],
        [Text(72, 72, "Vision language models answer questions.")],
    ]
)


async def upload(client: AsyncClient, data: bytes = PAPER) -> str:
    response = await client.post("/documents", files={"file": ("p.pdf", data, "application/pdf")})
    doc_id: str = response.json()["doc_id"]
    return doc_id


async def test_search_returns_ranked_page_tagged_hits(client: AsyncClient) -> None:
    doc_id = await upload(client)

    response = await client.post(
        f"/documents/{doc_id}/search", json={"query": "metamorphic relations"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "metamorphic relations"
    top = body["hits"][0]
    assert (top["page"], top["doc_id"]) == (1, doc_id)
    assert top["text"] == "Metamorphic relations expose hallucinations."
    assert top["keyword_rank"] == 1
    assert {"chunk_id", "bbox", "char_start", "char_end", "score", "vector_rank"} <= top.keys()


async def test_search_only_covers_the_selected_paper(client: AsyncClient) -> None:
    selected = await upload(client)
    await upload(client, make_pdf([[Text(72, 72, "Metamorphic testing of compilers.")]]))

    hits = (
        await client.post(f"/documents/{selected}/search", json={"query": "metamorphic"})
    ).json()["hits"]

    assert {h["doc_id"] for h in hits} == {selected}


async def test_top_k_limits_the_number_of_hits(client: AsyncClient) -> None:
    doc_id = await upload(client)

    response = await client.post(
        f"/documents/{doc_id}/search", json={"query": "models", "top_k": 1}
    )

    assert len(response.json()["hits"]) == 1


async def test_search_in_unknown_paper_is_a_404(client: AsyncClient) -> None:
    response = await client.post(f"/documents/{uuid.uuid4()}/search", json={"query": "x"})

    assert response.status_code == 404


@pytest.mark.parametrize("body", [{"query": ""}, {"query": "   "}, {"query": "ok", "top_k": 0}])
async def test_invalid_search_request_is_a_422(
    client: AsyncClient, body: dict[str, object]
) -> None:
    doc_id = await upload(client)

    response = await client.post(f"/documents/{doc_id}/search", json=body)

    assert response.status_code == 422
