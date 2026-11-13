from typing import Any

from langgraph.types import StreamWriter

from app.agent import prompts
from app.agent.state import AgentState, StreamingNode
from app.agent.token_filter import NotFoundFilter
from app.llm.base import LLMClient


def _ignore(_: Any) -> None:
    """Default writer for direct calls; inside a graph LangGraph injects the real one."""


def make_synthesize(llm: LLMClient) -> StreamingNode:
    async def synthesize(state: AgentState, *, writer: StreamWriter = _ignore) -> AgentState:
        prompt = prompts.SYNTHESIZE.format(
            passages=prompts.format_passages(state["passages"]),
            sub_questions=prompts.format_sub_questions(state.get("sub_questions", [])),
            question=state["question"],
            not_found=prompts.NOT_FOUND,
        )
        parts: list[str] = []
        hold_back = NotFoundFilter()
        async for chunk in llm.stream(prompt, tier="answer"):
            parts.append(chunk)
            if text := hold_back.feed(chunk):
                writer({"token": text})
        if text := hold_back.flush():
            writer({"token": text})
        return {"draft": "".join(parts)}

    return synthesize
