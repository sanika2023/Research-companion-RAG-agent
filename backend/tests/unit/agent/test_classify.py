from app.agent.nodes.classify import make_classify
from tests.conftest import FakeLLM


async def test_classify_uses_the_light_model_and_returns_the_kind() -> None:
    llm = FakeLLM({"Classify the question": '{"kind": "multi_step"}'})

    update = await make_classify(llm)({"question": "Compare A and B and explain why."})

    assert update["kind"] == "multi_step"
    assert llm.tiers == ["light"]
    assert "Compare A and B and explain why." in llm.prompts[0]


async def test_classify_falls_back_to_simple_when_the_model_fails() -> None:
    llm = FakeLLM({"Classify the question": "not json"})

    update = await make_classify(llm)({"question": "q"})

    assert update["kind"] == "simple"
    assert update["flags"] == ["classify_failed"]
