"""The agent's live event stream, end to end, with a fake LLM and a fake search."""

import json
from collections.abc import AsyncIterator

import pytest

from app.agent.events import AgentEvent, Finished, StepStarted, SubQuestions, Token
from app.agent.graph import build_agent, stream_answer
from app.core.config import AgentSettings
from app.llm.base import Tier
from app.llm.gemini import LLMUnavailableError
from tests.conftest import FakeLLM
from tests.unit.agent.helpers import FakeSearch, hit

SETTINGS = AgentSettings(max_sub_questions=4, max_passages=10)
QUESTION = "Which datasets does MetaQA use?"
PASSAGES = [hit("MetaQA is evaluated on TruthfulQA and HotpotQA.", page=9)]
SIMPLE = json.dumps({"kind": "simple"})


async def events_for(llm: FakeLLM, search: FakeSearch) -> list[AgentEvent]:
    return [event async for event in stream_answer(build_agent(llm, search, SETTINGS), QUESTION)]


def kinds(events: list[AgentEvent]) -> list[str]:
    """Event sequence with consecutive tokens collapsed, for readable assertions."""
    names = [e.step if isinstance(e, StepStarted) else type(e).__name__ for e in events]
    return [n for i, n in enumerate(names) if n != "Token" or names[i - 1 : i] != ["Token"]]


async def test_simple_question_streams_steps_then_tokens_then_the_checked_answer() -> None:
    llm = FakeLLM({"Classify the question": SIMPLE, "numbered passages": "TruthfulQA [1]."})

    events = await events_for(llm, FakeSearch({QUESTION: PASSAGES}))

    assert kinds(events) == ["classify", "retrieve", "synthesize", "Token", "Finished"]
    tokens = [e.text for e in events if isinstance(e, Token)]
    assert len(tokens) > 1
    final = events[-1]
    assert isinstance(final, Finished)
    assert "".join(tokens) == final.state["answer"] == "TruthfulQA [1]."
    assert [c.page for c in final.state["citations"]] == [9]


async def test_multi_step_question_announces_its_sub_questions_before_searching() -> None:
    llm = FakeLLM(
        {
            "Classify the question": json.dumps({"kind": "multi_step"}),
            "Break the question": json.dumps({"sub_questions": ["What datasets?"]}),
            "numbered passages": "Answer [1].",
        }
    )

    events = await events_for(llm, FakeSearch({QUESTION: PASSAGES}))

    assert kinds(events)[:4] == ["classify", "decompose", "SubQuestions", "retrieve"]
    assert SubQuestions(["What datasets?"]) in events


async def test_refusal_streams_no_tokens_and_finishes_refused() -> None:
    llm = FakeLLM({"Classify the question": SIMPLE})

    events = await events_for(llm, FakeSearch({}))

    assert kinds(events) == ["classify", "retrieve", "Finished"]
    final = events[-1]
    assert isinstance(final, Finished)
    assert final.state["refused"] is True


class BreaksMidAnswer(FakeLLM):
    async def stream(self, prompt: str, *, tier: Tier = "answer") -> AsyncIterator[str]:
        yield "Partial "
        raise LLMUnavailableError("overloaded")


async def test_model_outage_mid_answer_propagates_after_the_partial_tokens() -> None:
    llm = BreaksMidAnswer({"Classify the question": SIMPLE})
    received: list[AgentEvent] = []

    with pytest.raises(LLMUnavailableError):
        async for event in stream_answer(
            build_agent(llm, FakeSearch({QUESTION: PASSAGES}), SETTINGS), QUESTION
        ):
            received.append(event)
    assert Token("Partial ") in received
    assert not any(isinstance(e, Finished) for e in received)


async def test_failed_decomposition_announces_no_sub_questions() -> None:
    llm = FakeLLM(
        {"Classify the question": json.dumps({"kind": "multi_step"}), "numbered passages": "A [1]."}
    )  # no decomposition reply -> decompose fails and falls back to the original question

    events = await events_for(llm, FakeSearch({QUESTION: PASSAGES}))

    assert not any(isinstance(e, SubQuestions) for e in events)
