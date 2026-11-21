"""Compare keyword, vector, and hybrid search on the evaluation questions (no LLM calls).

Run from backend/:  uv run python -m app.evaluation.retrieval_run
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_embedder
from app.core.config import get_settings
from app.db.models import Chunk, Document
from app.db.session import get_sessionmaker
from app.evaluation.metrics import Rank, first_hit_rank
from app.evaluation.queries import Query, load_queries
from app.evaluation.report import retrieval_table
from app.retrieval.hybrid import hybrid_search
from app.retrieval.lexical import keyword_search
from app.retrieval.vector import vector_search

RESULTS_DIR = Path("../eval/results")
DEPTH = 10  # deepest rank inspected; the agent keeps at most 10 passages
KS = (1, 3, 5, 10)
METHODS = ("keyword", "vector", "hybrid")
WORDINGS = {"user": "Questions as a user would ask", "paper": "Same questions in the paper's terms"}

PerQuery = list[dict[str, object]]
Ranks = dict[str, dict[str, list[Rank]]]  # wording -> method -> one rank per question


def main() -> None:
    queries = [q for q in load_queries() if q.answerable]
    ranks, per_query = asyncio.run(_run(queries))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "retrieval.json").write_text(json.dumps(per_query, indent=2) + "\n")
    sections = [
        f"## {WORDINGS[wording]}\n\n{retrieval_table(by_method, ks=KS)}"
        for wording, by_method in ranks.items()
    ]
    report = (
        f"# Retrieval comparison\n\n{len(queries)} answerable questions; a hit means a passage "
        "from an expected page is in the top k.\n\n" + "\n\n".join(sections) + "\n"
    )
    (RESULTS_DIR / "retrieval.md").write_text(report)
    print(report)


def _wordings(query: Query) -> dict[str, str]:
    texts = {"user": query.question, "paper": query.paper_wording}
    return {wording: text for wording, text in texts.items() if text}


async def _run(queries: list[Query]) -> tuple[Ranks, PerQuery]:
    settings = get_settings()
    embedder = get_embedder()
    ranks: Ranks = {w: {m: [] for m in METHODS} for w in WORDINGS}
    per_query: PerQuery = []

    async with get_sessionmaker()() as session:
        doc_ids = await _doc_ids(session)
        for query in queries:
            doc_id = doc_ids[query.paper]
            expected = set(query.expected_pages)
            for wording, text in _wordings(query).items():
                [vector] = await embedder.embed([text])
                hits = await hybrid_search(
                    session,
                    embedder,
                    doc_id,
                    text,
                    top_k=DEPTH,
                    candidates=settings.retrieval_candidates,
                    rrf_k=settings.rrf_k,
                )
                keyword_ids = await keyword_search(session, doc_id, text, limit=DEPTH)
                vector_ids = await vector_search(session, doc_id, vector, limit=DEPTH)
                pages = {
                    "keyword": await _pages(session, keyword_ids),
                    "vector": await _pages(session, vector_ids),
                    "hybrid": [h.page for h in hits],
                }
                row: dict[str, object] = {"id": query.id, "type": query.type, "wording": wording}
                for method in METHODS:
                    rank = first_hit_rank(pages[method], expected=expected)
                    ranks[wording][method].append(rank)
                    row[method] = {"rank": rank, "pages": pages[method]}
                per_query.append(row)
    return ranks, per_query


async def _doc_ids(session: AsyncSession) -> dict[str, uuid.UUID]:
    rows = await session.execute(select(Document.filename, Document.id))
    return {filename: doc_id for filename, doc_id in rows}


async def _pages(session: AsyncSession, ids: list[uuid.UUID]) -> list[int]:
    """Page of each chunk id, keeping the ranking order."""
    rows = await session.execute(select(Chunk.id, Chunk.page).where(Chunk.id.in_(ids)))
    page_of = {chunk_id: page for chunk_id, page in rows}
    return [page_of[i] for i in ids]


if __name__ == "__main__":
    if sys.platform == "win32":  # psycopg async needs the selector loop on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()
