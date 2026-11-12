# 0003: Hybrid retrieval scoped to one paper

## Context
Users pick one paper and ask questions about it. Retrieval must find the passages that answer
a natural-language question, including exact terms (method names, datasets, acronyms) and
paraphrases, and must never return text from other papers.

## Decision
- **Every search is scoped to one document:** `POST /documents/{doc_id}/search`; 404 if the
  paper doesn't exist.
- **Keyword search:** Postgres full-text search. The question is stemmed with the `english`
  configuration and its terms are **OR-ed** (any term may match), ranked by `ts_rank_cd`.
  Terms are quoted, so user punctuation can't inject tsquery syntax.
- **Vector search:** cosine distance between the question's embedding and each chunk's,
  **exact** over the selected paper's chunks. Ordering by `(distance, chunk_index)` means the
  HNSW index can't serve the query, so Postgres filters by `doc_id` and sorts ~100 vectors.
- **Fusion:** Reciprocal Rank Fusion, `score = Σ 1/(k + rank)` with `k = 60`; each search
  contributes its top 40 candidates; the top 8 fused hits are returned (all configurable).
- **Auditability:** every hit reports its keyword rank and vector rank, so it is visible *why*
  a passage was retrieved.

## Alternatives considered
- **AND-ed keyword terms** (`plainto_tsquery`): precise, but a question with any word missing
  from a passage misses it entirely, which is common for natural-language questions. OR +
  ranking gives recall; fusion with vectors restores precision. (Not yet measured; AND vs. OR
  is a candidate comparison for the evaluation.)
- **HNSW approximate search with a `doc_id` filter:** HNSW filters *after* its approximate
  search, so other papers' chunks can crowd the selected paper out. Reproduced: with the index
  forced, a paper-scoped query returned 0 of 10 expected chunks. pgvector 0.8's iterative scan
  fixes this, but exact search over one paper is simpler, always correct, and fast at any
  corpus size. The HNSW index is kept for possible cross-paper search later.
- **Weighted score fusion** (normalize and add scores): needs tuning, and `ts_rank_cd` and
  cosine similarity are on unrelated scales. RRF uses ranks only, with no tuning.
- **True BM25** (e.g. ParadeDB `pg_search` extension): better lexical ranking, but needs a
  non-standard Postgres image that free hosts like Neon may not offer.
