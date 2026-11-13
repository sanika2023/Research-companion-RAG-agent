import json

from app.agent.nodes.decompose import make_decompose
from tests.conftest import FakeLLM


def llm_returning(*sub_questions: str) -> FakeLLM:
    return FakeLLM({"Break the question": json.dumps({"sub_questions": list(sub_questions)})})


async def test_decompose_returns_sub_questions_from_the_light_model() -> None:
    llm = llm_returning("What is A?", "What is B?")

    update = await make_decompose(llm, max_sub_questions=4)({"question": "A vs B?"})

    assert update["sub_questions"] == ["What is A?", "What is B?"]
    assert llm.tiers == ["light"]
    assert "at most 4" in llm.prompts[0]


async def test_decompose_caps_the_number_of_sub_questions() -> None:
    llm = llm_returning("q1", "q2", "q3")

    update = await make_decompose(llm, max_sub_questions=2)({"question": "q"})

    assert update["sub_questions"] == ["q1", "q2"]


async def test_decompose_drops_blank_and_duplicate_sub_questions() -> None:
    llm = llm_returning("q1", "  ", "q1", "q2")

    update = await make_decompose(llm, max_sub_questions=4)({"question": "q"})

    assert update["sub_questions"] == ["q1", "q2"]


async def test_decompose_failure_continues_without_sub_questions() -> None:
    update = await make_decompose(FakeLLM(), max_sub_questions=4)({"question": "q"})

    assert update["sub_questions"] == []
    assert update["flags"] == ["decompose_failed"]
