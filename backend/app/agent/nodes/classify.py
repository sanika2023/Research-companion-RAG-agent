from pydantic import BaseModel

from app.agent import prompts
from app.agent.state import AgentState, Node, QuestionKind
from app.llm.base import LLMClient
from app.llm.gemini import LLMUnavailableError


class Classification(BaseModel):
    kind: QuestionKind


def make_classify(llm: LLMClient) -> Node:
    async def classify(state: AgentState) -> AgentState:
        prompt = prompts.CLASSIFY.format(question=state["question"])
        try:
            result = await llm.complete_json(prompt, Classification, tier="light")
        except (LLMUnavailableError, ValueError):
            # Routing is an optimisation: a simple-path answer beats no answer.
            return {"kind": "simple", "flags": ["classify_failed"]}
        return {"kind": result.kind}

    return classify
