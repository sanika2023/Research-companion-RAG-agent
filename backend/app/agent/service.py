import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import answer_question, build_agent
from app.agent.state import AgentState
from app.core.config import AgentSettings, RetrievalSettings
from app.llm.base import Embedder, LLMClient
from app.retrieval.hybrid import SearchHit, hybrid_search


async def ask(
    question: str,
    *,
    doc_id: uuid.UUID,
    session: AsyncSession,
    llm: LLMClient,
    embedder: Embedder,
    retrieval: RetrievalSettings,
    agent_settings: AgentSettings,
) -> AgentState:
    """Answer a question about one paper; the agent can only search that paper."""

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

    return await answer_question(build_agent(llm, search, agent_settings), question)
