# Report notes

Running notes for the thesis report: what was built, why, and what to discuss as limitations.
Newest phase at the bottom. Formal design decisions live in `docs/decisions/` (ADRs).

---

## The big idea so far

A RAG system answers questions about documents in two halves:

1. **Offline (ingestion):** turn each PDF into small, searchable, *traceable* pieces of text.
2. **Online (question time):** find the pieces relevant to a question, then have an LLM answer
   using only those pieces, citing them.

Everything built so far is the foundation and the first half. The guiding requirement is
**auditability**: every answer must point back to an exact page (and region) of the source PDF,
so every stored piece of text carries its provenance.

---

## Phase 0 — Foundation (merged in PR #1)

**What was built**
- FastAPI backend skeleton with a `/health` endpoint, typed configuration from environment
  variables, and strict linting/type checking (ruff, mypy strict).
- Test-driven development from the first line: tests are written first and must fail for the
  right reason before code is written.
- Provider-agnostic interfaces (`LLMClient`, `Embedder`) with deterministic fakes, so unit tests
  never call a real model. This keeps tests fast, free, offline, and repeatable.
- PostgreSQL + pgvector in Docker. One database stores text, keyword index, and vectors.
- Schema: `documents` and `chunks`. Each chunk stores `page`, `chunk_index`, character offsets,
  bounding boxes, a 384-dim embedding, and a generated full-text-search column.
- Alembic migrations; the backend container migrates the database on startup, so
  `docker compose up` produces a working system from scratch.

**Design decisions worth explaining in the report** (see ADR 0001)
- **Hybrid search in a single database.** Postgres full-text search (keyword) and pgvector
  (semantic) live side by side, avoiding a separate search engine. Simpler to deploy for free.
- **Generated `tsvector` column.** Postgres keeps the keyword index in sync with the text
  automatically; the application cannot forget to update it.
- **HNSW vector index** rather than IVFFlat: no training step, works on a small, growing corpus.

**Limitations**
- Postgres full-text ranking (`ts_rank_cd`) is **not true BM25** (it lacks BM25's document-length
  normalization and term-saturation formula). The proposal says "BM25"; the report should say
  "BM25-style lexical ranking via Postgres full-text search" and note the difference.
- The embedding dimension (384) is fixed in the schema; changing embedding models requires a
  migration and re-embedding every chunk.

---

## Phase 1a — Ingestion: parsing and chunking (branch `feat/ingestion`)

**What ingestion does**
`PDF bytes → parse into text blocks with positions → split into chunks → embed → store`.
Parsing and chunking are done; embedding, storage, and the upload endpoint are next.

**Parsing (`ingestion/parse.py`, PyMuPDF)**
- Extracts each page's text *blocks* (roughly paragraphs) with bounding boxes
  `[x0, y0, x1, y1]` in PDF points, numbered from page 1 to match the viewer.
- Cleaning rules, each motivated by something observed in the sample papers:
  - **Rotated text is dropped.** arXiv stamps a vertical watermark
    (`arXiv:2404.10193v1 [cs.CV] 16 Apr 2024`) in the margin of page 1; it would otherwise
    pollute search results.
  - **Digit-only blocks are dropped** (page numbers, figure step markers like "1", "2 3").
  - **Line-break hyphens are rejoined** ("syn-" + "onymous" → "synonymous"). Without this,
    a keyword search for "synonymous" misses text broken across lines, which is common in
    narrow two-column layouts.
- Two-column reading order was checked on the samples: PyMuPDF returns the left column fully
  before the right column, so text does not interleave.

**Chunking (`ingestion/chunk.py`)**
- Sliding window of ~1,000 characters with ~150 characters of overlap, cut on word
  boundaries. Overlap means a sentence that straddles a boundary still appears whole in at
  least one chunk.
- **Chunks never cross a page boundary**, so every citation maps to exactly one page.
- Each chunk keeps character offsets into its page's text and the bounding boxes of the blocks
  it covers, so the viewer can highlight the cited region.
- Chunk size and overlap will be configurable, so they can be tuned during evaluation.
- Why ~1,000 characters: roughly 200–250 tokens, comfortably under the embedding model's
  512-token limit, and small enough that a citation points to a specific passage rather than
  a whole page.

**Results on the sample papers** (1,000 / 150)

| Paper | Layout | Pages | Chunks | Avg chars/chunk |
|---|---|---|---|---|
| Khan & Fu — consistency for black-box VQA | two-column | 15 | 74 | 901 |
| Wang & Ji — epistemic UQ for pre-trained NNs | two-column, math-heavy | 18 | 96 | 907 |
| Yang et al. — MetaQA hallucination detection | single-column (ACM) | 21 | 98 | 902 |

**Bugs found by testing** (useful as evidence that TDD caught real defects)
- The chunker emitted a duplicate tail chunk at the end of every page. Caught by the test
  asserting a short page produces exactly one chunk.
- Hyphenated words split across lines were found by inspecting real output, then fixed
  test-first.

**Limitations to discuss**
- **Figure text leaks into chunks.** Labels drawn inside vector figures (e.g. "box VLM",
  "consistent reliable") are extracted as ordinary text. Removing them reliably needs layout
  analysis (detecting figure regions). Effect: minor noise in search results.
- **Math is extracted poorly.** Equations come out as fragments of Unicode math symbols with
  missing spaces (e.g. `𝑅𝑆𝑖and 𝑅𝐴𝑗represent`). Questions about formulas will retrieve
  imperfect text; the PDF viewer still shows the true equation on the cited page.
- **Tables are flattened** into running text; row/column structure is lost.
- **Reading order depends on the PDF's internal structure.** It was correct for the samples,
  but unusual layouts (sidebars, multi-column figures, scanned PDFs) may not be. Scanned PDFs
  with no text layer produce no chunks at all (no OCR).
- **Cleaning heuristics have edge cases:**
  - Dropping rotated text would also drop legitimately rotated content (e.g. rotated table
    headers).
  - Dropping digit-only blocks could drop a standalone number that is real content.
  - Rejoining hyphens assumes a lowercase continuation means a split word, so a compound
    broken at its own hyphen ("self-" / "attention") becomes "selfattention".
- **Page-bounded chunks split paragraphs that continue onto the next page.** This trades some
  context for exact page citations.
- **Chunk size is measured in characters, not tokens.** It's simpler and deterministic, but only
  approximates the model's token budget.
- References sections are chunked like body text and may surface in search results.

---

## Ideas for the evaluation chapter
- Compare chunk sizes (e.g. 500 / 1,000 / 1,500) on retrieval quality for the eval queries.
- Measure how often the correct page appears in the top-k retrieved chunks (page-level recall).
- Include formula-heavy questions to quantify the math-extraction limitation.
