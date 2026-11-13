"""The question-answering agent as a LangGraph state machine.

classify ─► [decompose if multi-step] ─► retrieve ─► synthesize ─► check_citations
                                              └─ nothing found ─► refuse
"""

from typing import Any, Literal, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.check_citations import check_citations
from app.agent.nodes.classify import make_classify
from app.agent.nodes.decompose import make_decompose
from app.agent.nodes.refuse import refuse
from app.agent.nodes.retrieve import make_retrieve
from app.agent.nodes.synthesize import make_synthesize
from app.agent.state import AgentState, Search
from app.core.config import AgentSettings
from app.llm.base import LLMClient

Agent = CompiledStateGraph[AgentState, Any, AgentState, AgentState]


def build_agent(llm: LLMClient, search: Search, settings: AgentSettings) -> Agent:
    graph = StateGraph(AgentState)
    graph.add_node("classify", make_classify(llm))
    graph.add_node("decompose", make_decompose(llm, max_sub_questions=settings.max_sub_questions))
    graph.add_node("retrieve", make_retrieve(search, max_passages=settings.max_passages))
    graph.add_node("synthesize", make_synthesize(llm))
    graph.add_node("check_citations", check_citations)
    graph.add_node("refuse", refuse)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", _after_classify)
    graph.add_edge("decompose", "retrieve")
    graph.add_conditional_edges("retrieve", _after_retrieve)
    graph.add_edge("synthesize", "check_citations")
    graph.add_edge("check_citations", END)
    graph.add_edge("refuse", END)
    return graph.compile()


def _after_classify(state: AgentState) -> Literal["decompose", "retrieve"]:
    return "decompose" if state["kind"] == "multi_step" else "retrieve"


def _after_retrieve(state: AgentState) -> Literal["synthesize", "refuse"]:
    # Never let the model answer from no evidence: it would answer from memory, uncited.
    return "synthesize" if state["passages"] else "refuse"


async def answer_question(agent: Agent, question: str) -> AgentState:
    return cast(AgentState, await agent.ainvoke({"question": question, "flags": []}))
