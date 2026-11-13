from itertools import chain, zip_longest

from app.agent.state import AgentState, Node, Search
from app.retrieval.hybrid import SearchHit


def make_retrieve(search: Search, *, max_passages: int) -> Node:
    async def retrieve(state: AgentState) -> AgentState:
        queries = list(dict.fromkeys([state["question"], *state.get("sub_questions", [])]))
        results = [await search(q) for q in queries]
        return {"passages": _interleave_unique(results, max_passages)}

    return retrieve


def _interleave_unique(results: list[list[SearchHit]], limit: int) -> list[SearchHit]:
    """Round-robin over each query's ranked hits so every sub-question gets passages."""
    seen: set[object] = set()
    passages: list[SearchHit] = []
    for hit in chain.from_iterable(zip_longest(*results)):
        if hit is None or hit.chunk_id in seen:
            continue
        seen.add(hit.chunk_id)
        passages.append(hit)
        if len(passages) == limit:
            break
    return passages
