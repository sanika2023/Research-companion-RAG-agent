from pydantic import BaseModel

from app.agent import prompts
from app.agent.state import AgentState, Node
from app.llm.base import LLMClient
from app.llm.gemini import LLMUnavailableError


class Decomposition(BaseModel):
    sub_questions: list[str]


def make_decompose(llm: LLMClient, *, max_sub_questions: int) -> Node:
    async def decompose(state: AgentState) -> AgentState:
        prompt = prompts.DECOMPOSE.format(
            question=state["question"], max_sub_questions=max_sub_questions
        )
        try:
            result = await llm.complete_json(prompt, Decomposition, tier="light")
        except (LLMUnavailableError, ValueError):
            # Retrieval still runs on the original question.
            return {"sub_questions": [], "flags": ["decompose_failed"]}
        cleaned = list(dict.fromkeys(q.strip() for q in result.sub_questions if q.strip()))
        return {"sub_questions": cleaned[:max_sub_questions]}

    return decompose
