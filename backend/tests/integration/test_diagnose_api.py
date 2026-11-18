import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.deps import get_llm
from app.llm.base import M, Tier
from app.llm.gemini import LLMUnavailableError
from app.main import app
from tests.conftest import FakeLLM
from tests.integration.seed import SeededPaper, seed_paper

pytestmark = pytest.mark.integration

TEXTS = [
    "MetaQA is evaluated on TruthfulQA and HotpotQA.",
    "MetaQA uses metamorphic relations to detect hallucinations.",
    "The appendix lists the prompts.",
]
ANSWER = "MetaQA uses metamorphic relations [1]."
JUDGEMENT = json.dumps(
    {
        "claims": ["MetaQA uses metamorphic relations."],
        "answers": [
            {"id": kind, "verdicts": ["agrees"]}
            for kind in ("paraphrase", "reorder", "distractor", "drop_cited")
        ],
    }
)
STABLE = {
    "agree with an original answer": JUDGEMENT,
    "Rewrite the question": "How does MetaQA detect hallucinations?",
    "numbered passages": ANSWER,
}


def use_llm(llm: object) -> None:
    app.dependency_overrides[get_llm] = lambda: llm


def request(paper: SeededPaper, **overrides: Any) -> dict[str, Any]:
    body = {
        "question": "What does MetaQA use?",
        "answer": ANSWER,
        "passage_ids": [str(paper.chunk_ids[1]), str(paper.chunk_ids[0])],
    }
    return body | overrides


async def test_diagnose_scores_an_answer_with_a_breakdown_per_perturbation(
    client: AsyncClient, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    use_llm(FakeLLM(STABLE))

    response = await client.post(f"/documents/{paper.doc_id}/diagnose", json=request(paper))

    assert response.status_code == 200
    body = response.json()
    assert body["doc_id"] == str(paper.doc_id)
    assert body["uncertainty"] == pytest.approx(0.0)
    assert body["claims"] == ["MetaQA uses metamorphic relations."]
    signals = {s["kind"]: s for s in body["signals"]}
    assert signals.keys() == {"paraphrase", "reorder", "distractor", "drop_cited"}
    assert all(s["status"] == "ok" for s in signals.values())
    assert signals["paraphrase"]["question"] == "How does MetaQA detect hallucinations?"
    assert signals["drop_cited"]["weight"] == 0.0


async def test_diagnose_uses_an_unseen_passage_of_the_paper_as_the_distractor(
    client: AsyncClient, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    llm = FakeLLM(STABLE)
    use_llm(llm)

    await client.post(f"/documents/{paper.doc_id}/diagnose", json=request(paper))

    # The only passage not sent is the appendix, so it must be the distractor.
    assert sum("The appendix lists the prompts." in p for p in llm.prompts) == 1


async def test_diagnose_in_unknown_paper_is_a_404(
    client: AsyncClient, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    response = await client.post(f"/documents/{uuid.uuid4()}/diagnose", json=request(paper))

    assert response.status_code == 404


async def test_diagnose_with_a_passage_from_another_paper_is_a_422(
    client: AsyncClient, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    other = await seed_paper(async_engine, ["Elsewhere."], filename="other.pdf")

    response = await client.post(
        f"/documents/{paper.doc_id}/diagnose",
        json=request(paper, passage_ids=[str(other.chunk_ids[0])]),
    )

    assert response.status_code == 422


async def test_diagnose_without_passages_is_a_422(
    client: AsyncClient, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)

    response = await client.post(
        f"/documents/{paper.doc_id}/diagnose", json=request(paper, passage_ids=[])
    )

    assert response.status_code == 422


class UnavailableLLM(FakeLLM):
    async def complete(self, prompt: str, *, tier: Tier = "answer") -> str:
        raise LLMUnavailableError("overloaded")

    async def complete_json(self, prompt: str, schema: type[M], *, tier: Tier = "light") -> M:
        raise LLMUnavailableError("overloaded")


async def test_diagnose_during_a_model_outage_is_a_503(
    client: AsyncClient, async_engine: AsyncEngine
) -> None:
    paper = await seed_paper(async_engine, TEXTS)
    use_llm(UnavailableLLM())

    response = await client.post(f"/documents/{paper.doc_id}/diagnose", json=request(paper))

    assert response.status_code == 503
    assert "try again" in response.json()["detail"].lower()
