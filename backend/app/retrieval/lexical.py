import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Postgres' own parsers turn the question into stemmed lexemes; we then OR them together.
# plainto_tsquery would AND them, so a natural-language question with one word absent from
# a chunk would miss it entirely. quote_literal keeps user punctuation from becoming syntax.
# 'simple' avoids re-stemming lexemes that are already stemmed.
_KEYWORD_SQL = text("""
    WITH q AS (
        SELECT to_tsquery('simple', coalesce(string_agg(quote_literal(lexeme), ' | '), '')) AS query
        FROM unnest(tsvector_to_array(to_tsvector('english', :query))) AS lexeme
    )
    SELECT c.id
    FROM chunks c, q
    WHERE c.doc_id = :doc_id AND c.tsv @@ q.query
    ORDER BY ts_rank_cd(c.tsv, q.query) DESC, c.chunk_index
    LIMIT :limit
""")


async def keyword_search(
    session: AsyncSession, doc_id: uuid.UUID, query: str, limit: int
) -> list[uuid.UUID]:
    """Chunk ids of one paper ranked by full-text relevance (BM25-style, not true BM25)."""
    rows = await session.execute(_KEYWORD_SQL, {"query": query, "doc_id": doc_id, "limit": limit})
    return list(rows.scalars())
