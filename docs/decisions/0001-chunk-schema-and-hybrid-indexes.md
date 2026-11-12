# 0001: Chunk schema and hybrid-search indexes

## Context
Hybrid search needs both keyword and vector retrieval over the same chunks, and every
citation must link back to an exact page and region in the PDF viewer.

## Decision
- Single Postgres database with pgvector; no separate search service.
- `chunks` keeps provenance: `doc_id`, `page` (1-based), `chunk_index`, `char_start/end`, and
  `bbox` (JSONB list of `[x0, y0, x1, y1]` boxes) so the viewer can highlight the cited span.
- `tsv` is a **generated** `tsvector` column (`to_tsvector('english', text)`), so keyword
  search cannot drift out of sync with the text. GIN index.
- `embedding` is `vector(384)` (bge-small-en-v1.5) with an **HNSW** cosine index.
- Lexical ranking uses Postgres full-text search (`ts_rank_cd`), which is not true BM25
  (no document-length normalization of the same form). Noted as a limitation for the thesis.
- Schema changes go through Alembic; the backend container runs `alembic upgrade head` on boot.

## Alternatives considered
- **IVFFlat index:** needs a training step and data present at build time; HNSW works on a
  small, growing corpus.
- **Separate BM25 engine (Elasticsearch, `pg_bm25`):** truer BM25, but extra infrastructure
  that complicates `docker compose up` and free-tier deployment.
- **Application-maintained `tsvector`:** more code and a risk of stale rows.

## Consequences
Changing the embedding model's dimension requires a new migration and re-embedding all chunks.
Docker maps Postgres to host port 5433 because a native Postgres may already occupy 5432.
