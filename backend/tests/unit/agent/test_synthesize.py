from app.agent.nodes.synthesize import make_synthesize
from app.agent.state import AgentState
from tests.conftest import FakeLLM
from tests.unit.agent.helpers import hit


async def test_synthesize_prompts_the_answer_model_with_numbered_passages() -> None:
    llm = FakeLLM({"numbered passages": "MetaQA uses metamorphic relations [1]."})
    state: AgentState = {
        "question": "What does MetaQA use?",
        "passages": [hit("MetaQA uses MRs.", page=3), hit("Other text.", page=7)],
    }

    update = await make_synthesize(llm)(state)

    assert update["draft"] == "MetaQA uses metamorphic relations [1]."
    assert llm.tiers == ["answer"]
    prompt = llm.prompts[0]
    assert "[1] (page 3)\nMetaQA uses MRs." in prompt
    assert "[2] (page 7)\nOther text." in prompt
    assert "What does MetaQA use?" in prompt


async def test_synthesize_asks_to_cover_the_sub_questions() -> None:
    llm = FakeLLM()
    state: AgentState = {"question": "q", "passages": [hit("p")], "sub_questions": ["What is A?"]}

    await make_synthesize(llm)(state)

    assert "- What is A?" in llm.prompts[0]
