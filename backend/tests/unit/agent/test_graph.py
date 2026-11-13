"""The whole agent, end to end, with a fake LLM and a fake search (no network, no database)."""

import json

from app.agent.graph import answer_question, build_agent
from app.agent.nodes.check_citations import NOT_FOUND_MESSAGE
from app.agent.prompts import NOT_FOUND
from app.core.config import AgentSettings
from tests.conftest import FakeLLM
from tests.unit.agent.helpers import FakeSearch, hit

SETTINGS = AgentSettings(max_sub_questions=4, max_passages=10)
QUESTION = "Which datasets does MetaQA use?"
PASSAGES = [hit("MetaQA is evaluated on TruthfulQA and HotpotQA.", page=9)]


def classified(kind: str, **more: str) -> FakeLLM:
    return FakeLLM({"Classify the question": json.dumps({"kind": kind}), **more})


async def test_simple_question_is_answered_with_page_citations() -> None:
    llm = classified("simple", **{"numbered passages": "TruthfulQA and HotpotQA [1]."})
    agent = build_agent(llm, FakeSearch({QUESTION: PASSAGES}), SETTINGS)

    result = await answer_question(agent, QUESTION)

    assert result["answer"] == "TruthfulQA and HotpotQA [1]."
    assert [(c.number, c.page) for c in result["citations"]] == [(1, 9)]
    assert result["refused"] is False
    assert llm.tiers == ["light", "answer"]  # classify, then synthesize; no decomposition


async def test_multi_step_question_is_decomposed_and_each_part_is_searched() -> None:
    decomposition = json.dumps({"sub_questions": ["What datasets?", "Why those?"]})
    llm = classified(
        "multi_step",
        **{"Break the question": decomposition, "numbered passages": "Answer [1]."},
    )
    search = FakeSearch({QUESTION: PASSAGES})
    agent = build_agent(llm, search, SETTINGS)

    result = await answer_question(agent, QUESTION)

    assert result["sub_questions"] == ["What datasets?", "Why those?"]
    assert search.queries == [QUESTION, "What datasets?", "Why those?"]
    assert "- Why those?" in llm.prompts[-1]


async def test_nothing_retrieved_refuses_without_calling_the_answer_model() -> None:
    llm = classified("simple")
    agent = build_agent(llm, FakeSearch({}), SETTINGS)

    result = await answer_question(agent, QUESTION)

    assert result["refused"] is True
    assert result["answer"] == NOT_FOUND_MESSAGE
    assert llm.tiers == ["light"]


async def test_model_saying_not_found_is_a_refusal() -> None:
    llm = classified("simple", **{"numbered passages": NOT_FOUND})
    agent = build_agent(llm, FakeSearch({QUESTION: PASSAGES}), SETTINGS)

    result = await answer_question(agent, QUESTION)

    assert result["refused"] is True
    assert result["citations"] == []


async def test_flags_from_different_steps_accumulate() -> None:
    llm = FakeLLM({"numbered passages": "No citations here."})  # classify reply missing
    agent = build_agent(llm, FakeSearch({QUESTION: PASSAGES}), SETTINGS)

    result = await answer_question(agent, QUESTION)

    assert result["flags"] == ["classify_failed", "uncited"]
