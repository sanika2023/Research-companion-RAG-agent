import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient

from app.llm.base import Tier
from app.llm.gemini import LLMUnavailableError
from tests.conftest import FakeLLM
from tests.integration.test_ask_api import SIMPLE, upload, use_llm

pytestmark = pytest.mark.integration

QUESTION = {"question": "Which datasets does MetaQA use?"}


def parse_sse(body: str) -> list[tuple[str, Any]]:
    """(event, decoded data) pairs; keep-alive comments (lines starting with ':') skipped."""
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if not line.startswith(":")
        )
        if fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


async def stream(client: AsyncClient, doc_id: str) -> tuple[str, list[tuple[str, Any]]]:
    async with client.stream("POST", f"/documents/{doc_id}/ask/stream", json=QUESTION) as r:
        assert r.status_code == 200
        body = "".join([chunk async for chunk in r.aiter_text()])
        return r.headers["content-type"], parse_sse(body)


async def test_stream_sends_steps_tokens_and_the_cited_answer(client: AsyncClient) -> None:
    doc_id = await upload(client)
    use_llm(FakeLLM({"Classify the question": SIMPLE, "numbered passages": "TruthfulQA [1]."}))

    content_type, events = await stream(client, doc_id)

    assert content_type.startswith("text/event-stream")
    names = [name for name, _ in events]
    assert names[:3] == ["status", "status", "status"]
    assert [data["step"] for _, data in events[:3]] == ["classify", "retrieve", "synthesize"]
    tokens = [data["text"] for name, data in events if name == "token"]
    assert "".join(tokens) == "TruthfulQA [1]."
    final_name, final = events[-1]
    assert final_name == "done"
    assert final["answer"] == "TruthfulQA [1]."
    assert final["doc_id"] == doc_id
    assert [c["page"] for c in final["citations"]] == [2]


async def test_stream_for_unknown_paper_is_a_404_before_streaming(client: AsyncClient) -> None:
    response = await client.post(f"/documents/{uuid.uuid4()}/ask/stream", json=QUESTION)

    assert response.status_code == 404


async def test_stream_with_blank_question_is_a_422(client: AsyncClient) -> None:
    doc_id = await upload(client)

    response = await client.post(f"/documents/{doc_id}/ask/stream", json={"question": " "})

    assert response.status_code == 422


class BreaksMidAnswer(FakeLLM):
    async def stream(self, prompt: str, *, tier: Tier = "answer") -> AsyncIterator[str]:
        yield "Partial "
        raise LLMUnavailableError("overloaded")


async def test_model_outage_mid_stream_ends_with_an_error_event(client: AsyncClient) -> None:
    doc_id = await upload(client)
    use_llm(BreaksMidAnswer({"Classify the question": SIMPLE}))

    _, events = await stream(client, doc_id)

    names = [name for name, _ in events]
    assert "token" in names
    assert names[-1] == "error"
    assert "try again" in events[-1][1]["message"].lower()
    assert "done" not in names


class Crashes(FakeLLM):
    async def stream(self, prompt: str, *, tier: Tier = "answer") -> AsyncIterator[str]:
        raise RuntimeError("bug")
        yield  # pragma: no cover  # makes this an async generator


async def test_unexpected_error_mid_stream_still_ends_with_an_error_event(
    client: AsyncClient,
) -> None:
    doc_id = await upload(client)
    use_llm(Crashes({"Classify the question": SIMPLE}))

    _, events = await stream(client, doc_id)

    assert events[-1][0] == "error"
    assert "bug" not in events[-1][1]["message"]  # internals stay in the server log
