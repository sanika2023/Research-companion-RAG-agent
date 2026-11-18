import json
import uuid

import pytest
from httpx import AsyncClient

from app.api.deps import get_llm
from app.llm.base import M, Tier
from app.llm.gemini import LLMUnavailableError
from app.main import app
from tests.conftest import FakeLLM
from tests.pdf_factory import Text, make_pdf

pytestmark = pytest.mark.integration

PAPER = make_pdf(
    [
        [Text(72, 72, "Introduction to hallucination detection.")],
        [Text(72, 72, "MetaQA is evaluated on TruthfulQA and HotpotQA.")],
    ]
)
SIMPLE = json.dumps({"kind": "simple"})


async def upload(client: AsyncClient) -> str:
    response = await client.post("/documents", files={"file": ("p.pdf", PAPER, "application/pdf")})
    doc_id: str = response.json()["doc_id"]
    return doc_id


def use_llm(llm: object) -> None:
    app.dependency_overrides[get_llm] = lambda: llm


async def test_ask_returns_an_answer_with_page_citations(client: AsyncClient) -> None:
    doc_id = await upload(client)
    use_llm(FakeLLM({"Classify the question": SIMPLE, "numbered passages": "TruthfulQA [1]."}))

    response = await client.post(
        f"/documents/{doc_id}/ask", json={"question": "Which datasets does MetaQA use?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "TruthfulQA [1]."
    assert body["refused"] is False
    [citation] = body["citations"]
    assert citation["number"] == 1
    assert citation["page"] == 2  # the passage the fake answer cites, as ranked by real search
    assert citation["text"] == "MetaQA is evaluated on TruthfulQA and HotpotQA."
    assert {"chunk_id", "bbox"} <= citation.keys()
    assert body["flags"] == []


async def test_ask_lists_every_passage_the_model_saw_for_later_inspection(
    client: AsyncClient,
) -> None:
    doc_id = await upload(client)
    use_llm(FakeLLM({"Classify the question": SIMPLE, "numbered passages": "TruthfulQA [1]."}))

    body = (
        await client.post(f"/documents/{doc_id}/ask", json={"question": "Which datasets?"})
    ).json()

    # Both pages are retrieved, but only the cited one becomes a citation.
    assert len(body["passage_ids"]) == 2
    assert body["passage_ids"][0] == body["citations"][0]["chunk_id"]


async def test_ask_in_unknown_paper_is_a_404(client: AsyncClient) -> None:
    response = await client.post(f"/documents/{uuid.uuid4()}/ask", json={"question": "q"})

    assert response.status_code == 404


async def test_blank_question_is_a_422(client: AsyncClient) -> None:
    doc_id = await upload(client)

    response = await client.post(f"/documents/{doc_id}/ask", json={"question": "  "})

    assert response.status_code == 422


class UnavailableLLM(FakeLLM):
    async def complete(self, prompt: str, *, tier: Tier = "answer") -> str:
        raise LLMUnavailableError("overloaded")

    async def complete_json(self, prompt: str, schema: type[M], *, tier: Tier = "light") -> M:
        raise LLMUnavailableError("overloaded")


async def test_model_outage_is_a_503_with_a_clear_message(client: AsyncClient) -> None:
    doc_id = await upload(client)
    use_llm(UnavailableLLM())

    response = await client.post(f"/documents/{doc_id}/ask", json={"question": "q"})

    assert response.status_code == 503
    assert "try again" in response.json()["detail"].lower()
