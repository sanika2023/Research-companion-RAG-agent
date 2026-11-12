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
Phase 1a covers parsing and chunking; Phase 1b covers embedding, storage, and the upload API.

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
| Wang & Ji — epistemic UQ for pre-trained NNs | two-column, math-heavy | 18 | 94 | 907 |
| Yang et al. — MetaQA hallucination detection | single-column (ACM) | 21 | 97 | 902 |

(Counts are after the hyphen fix; rejoining split words shortened the text slightly, from
96 and 98 chunks before. Avg chars/chunk was measured before the fix.)

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

## Phase 1b — Ingestion: embedding, storage, upload API (branch `feat/ingestion`)

**What was built** (see ADR 0002)
- `FastEmbedEmbedder`: bge-small-en-v1.5 running locally via ONNX (no GPU, no API key). Each
  chunk becomes a 384-number vector; texts with similar meaning get nearby vectors, which is
  what semantic search will compare. Embedding runs in a worker thread so the async server
  keeps answering other requests meanwhile.
- `ingest_pdf` pipeline: parse → chunk → embed → store, in **one database transaction**.
  The original PDF is saved as `{doc_id}.pdf` for the viewer. If anything fails (bad PDF,
  disk error), the transaction rolls back: no half-ingested papers.
- API: `POST /documents` (upload, returns doc id + page/chunk counts) and `GET /documents`
  (list with chunk counts). Bad files → 400, oversize → 413 (`MAX_UPLOAD_MB`, default 50).
  Filenames are reduced to their base name, so a client can't send `../../x.pdf`.
- Chunk size/overlap are environment settings, validated at startup (overlap < size), so
  the evaluation can compare chunk sizes without code changes.
- Docker: the embedding model (65 MB) is downloaded at image build time; uploaded PDFs live
  in a named volume so they survive rebuilds.
- Testing: unit tests use a deterministic fake embedder; integration tests run the pipeline
  and API against a real Postgres test database. One integration test loads the real model
  and checks that related sentences are closer than unrelated ones.

**Results** (Docker, laptop CPU, 1000 / 150)

| Paper | Pages | Chunks | Upload time |
|---|---|---|---|
| Khan & Fu (black-box VQA) | 15 | 74 | 14 s |
| Wang & Ji (epistemic UQ) | 18 | 94 | 24 s |
| Yang et al. (MetaQA) | 21 | 97 | 21 s |

Parsing + chunking takes ~0.2 s per paper; **embedding is ~95% of ingestion time**
(~0.17 s per chunk on CPU). Smaller embedding batches helped only slightly (16 s → 12 s).

**Bugs found by testing**
- Reading the new document's id after `commit()` crashed under async SQLAlchemy (committed
  objects are expired, and reloading would need a hidden synchronous query). Caught by the
  pipeline integration tests; fixed by reading the id before committing.
- A test simulating a disk-write failure confirmed the rollback leaves no orphan rows.

**Limitations to discuss**
- **Ingestion is synchronous:** the upload request waits ~15–25 s. Free-tier hosts have
  slower CPUs, so this may approach request timeouts there. A background job with a status
  endpoint is the standard fix (deferred).
- **No duplicate detection:** uploading the same paper twice stores it twice.
- **Uploaded PDFs are on local disk.** Free container hosts typically have ephemeral disks,
  so stored PDFs may vanish on restart in the deployed version (to resolve in Phase 4).
- **No OCR:** scanned PDFs are rejected with a clear error rather than ingested.
- **Development environment note:** TLS-intercepting software on the dev machine blocked the
  model download from Hugging Face (certificate not trusted by Python); worked around once
  with the Windows certificate store. Not an issue inside Docker.

---

## Phase 2 — Hybrid retrieval (branch `feat/hybrid-retrieval`)

**What was built** (see ADR 0003)
- **Paper-scoped search:** the user selects one paper; `POST /documents/{doc_id}/search`
  only ever looks at that paper's chunks.
- **Keyword search** (Postgres full-text): stems the question ("hallucinations detected"
  matches "hallucination detection") and matches chunks containing *any* question term,
  ranking chunks with more matches higher.
- **Vector search** (pgvector): compares the question's embedding with each chunk's, exactly.
- **Reciprocal Rank Fusion:** `score = 1/(60 + keyword rank) + 1/(60 + vector rank)`.
  Uses ranks, not raw scores, because the two searches score on unrelated scales.
- **Each hit reports both ranks**, e.g. `p13 (keyword #4, vector #8)`, so the system can
  show *why* a passage was retrieved. This supports the auditability goal and the later
  diagnostics view.
- Search takes ~0.3 s (only the question is embedded; chunks were embedded at upload).

**Why keyword terms are OR-ed:** Postgres' default (`plainto_tsquery`) requires *every*
word. For natural-language questions, a passage missing even one word is excluded entirely.
OR gives recall; the ranking and fusion with vector search provide precision.

**Finding: approximate vector search can silently miss the selected paper.** The HNSW index
finds the nearest chunks across *all* papers first, then filters to the selected paper. With
the index forced on, a query whose nearest neighbours were in another paper returned **0 of
10** chunks of the selected paper (pgvector default) vs. 10 of 10 with iterative scanning.
The design avoids the problem entirely by searching the selected paper exactly (it has only
~100 chunks), which is correct by construction and fast at any number of papers. A test
reproduces the crowding scenario and fails if the query ever switches to the approximate index.

**Qualitative comparison on the sample papers** (top 3 per method)

| Question (paper) | Keyword only | Vector only | Hybrid |
|---|---|---|---|
| How does MetaQA compare to SelfCheckGPT? (MetaQA) | intro, RQ4, results | RQ4, results | RQ4, results, **p13 "MetaQA outperforms SelfCheckGPT in all seven categories"** (keyword #4, vector #8: in neither top 3) |
| Which datasets were used? (MetaQA) | related work, figure caption | **dataset section (HotpotQA, FreshQA)** | related work + **dataset section** |
| What is the rephrasing strategy? (Khan & Fu) | appendix, figure caption (weak) | **method section (p4)** | **method section ×2**, appendix |
| What gradient-based method is proposed? (Wang & Ji) | contribution (p2) | discussion (p17), contribution | both |

Takeaways: fusion can surface a passage that both methods rank moderately but neither ranks
highly; vector search covers keyword search's misses on paraphrased questions, and keyword
search anchors exact terms ("SelfCheckGPT", "gradient-based").

**Bugs found by testing / experiments**
- A test meant to reproduce index crowding passed even with the protection removed: the test
  used 60 *identical* vectors, which HNSW collapses into one graph entry. Using 60 distinct
  nearby vectors made the test fail as intended. (Lesson: verify a test can fail.)
- Initial RRF test expectation had an exact tie (1/(1+1) = 2/(1+3)); caught before
  implementation and corrected.

**Limitations to discuss**
- **Running headers leak into chunks.** The MetaQA paper repeats its title and author line on
  every page; that text lands in chunks, so keyword search matches title words on unrelated
  pages (p5, p7 for a "metamorphic relations" query). Fix: drop text blocks that repeat at the
  same position across most pages (ingestion change; not yet done).
- Keyword ranking is `ts_rank_cd`, not true BM25 (see Phase 0).
- English stemming only; non-English papers get weaker keyword search.
- bge-small recommends a query instruction prefix ("Represent this sentence for searching
  relevant passages: "); not used yet. Worth measuring in the evaluation.
- RRF constants (k = 60, 40 candidates, top 8) are standard defaults, not tuned.

---

## Ideas for the evaluation chapter
- Compare chunk sizes (e.g. 500 / 1,000 / 1,500) on retrieval quality for the eval queries.
- Measure how often the correct page appears in the top-k retrieved chunks (page-level recall).
- Include formula-heavy questions to quantify the math-extraction limitation.
- Report ingestion time per paper (and per chunk) locally vs. on the deployed host.
- Ablation: keyword-only vs. vector-only vs. hybrid on the eval queries (hit rate of the
  correct page in the top k). The search code already exposes each method separately.
- With vs. without the bge query prefix; RRF k (e.g. 10 / 60) and candidate depth.
- Effect of removing running headers/footers on keyword precision.
