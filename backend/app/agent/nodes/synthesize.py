from app.agent import prompts
from app.agent.state import AgentState, Node
from app.llm.base import LLMClient


def make_synthesize(llm: LLMClient) -> Node:
    async def synthesize(state: AgentState) -> AgentState:
        prompt = prompts.SYNTHESIZE.format(
            passages=prompts.format_passages(state["passages"]),
            sub_questions=prompts.format_sub_questions(state.get("sub_questions", [])),
            question=state["question"],
            not_found=prompts.NOT_FOUND,
        )
        return {"draft": await llm.complete(prompt, tier="answer")}

    return synthesize
