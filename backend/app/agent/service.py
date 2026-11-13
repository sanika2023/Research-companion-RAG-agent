import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.events import AgentEvent
from app.agent.graph import Agent, answer_question, build_agent, stream_answer
from app.agent.state import AgentState
from app.core.config import AgentSettings, RetrievalSettings
from app.llm.base import Embedder, LLMClient
from app.retrieval.hybrid import SearchHit, hybrid_search


def paper_agent(
    *,
    doc_id: uuid.UUID,
    session: AsyncSession,
    llm: LLMClient,
    embedder: Embedder,
    retrieval: RetrievalSettings,
    agent_settings: AgentSettings,
) -> Agent:
    """An agent whose only search tool is bound to one paper."""

    async def search(query: str) -> list[SearchHit]:
        return await hybrid_search(
            session,
            embedder,
            doc_id,
            query,
            top_k=retrieval.top_k,
            candidates=retrieval.candidates,
            rrf_k=retrieval.rrf_k,
        )

    return build_agent(llm, search, agent_settings)


async def ask(question: str, agent: Agent) -> AgentState:
    return await answer_question(agent, question)


def ask_stream(question: str, agent: Agent) -> AsyncIterator[AgentEvent]:
    return stream_answer(agent, question)
