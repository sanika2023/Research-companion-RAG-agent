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

## Phase 3 — Agent with cited answers (branch `feat/agent`)

**What was built** (see ADR 0004)
- A LangGraph agent: `classify → [decompose] → retrieve → synthesize → check_citations`, or
  `refuse` when retrieval finds nothing. `POST /documents/{doc_id}/ask` returns the answer,
  citations (number, page, chunk id, text, bbox), sub-questions, a refusal flag, and audit
  flags.
- **Citation verification in code:** the model's `[n]` markers are checked against the
  passages it was actually shown; invented ones are removed and flagged; answers with no
  valid citation are flagged `uncited`. This turns "the model says it cited something" into
  "the system verified every citation points to real retrieved text".
- **Refusal:** with no relevant passages, the model is never called; if passages exist but
  don't answer the question, the model is instructed to reply `NOT_FOUND`.
- Gemini client with two tiers (Flash-Lite for routing, Flash for answers), structured JSON
  output for routing, retries with backoff on 429/500/503, and a request deadline.
- All agent logic is tested with a fake LLM and fake search (no network): 22 node/graph tests
  plus API integration tests against the real database.

**Results** (Docker; Flash-Lite for both tiers because Flash was overloaded, see below)

| Question (paper) | Type | Time | Outcome |
|---|---|---|---|
| Which datasets were used to evaluate MetaQA? | simple | 2.8 s | TruthfulQA(-Enhanced), HotpotQA, FreshQA; 3 citations, each verified to mention all three |
| How does MetaQA compare to SelfCheckGPT, and why? | multi (2 sub-q) | 3.3 s | comparison + reasons, 5 citations incl. p13 "outperforms in all seven categories" |
| What is the rephrasing strategy? (Khan & Fu) | simple | 2.3 s | VQG-generated rephrasings, nucleus sampling p = 0.9; 3 citations |
| Why can't the method use model internals, and what instead? | multi (2) | 5.8 s | API-only black boxes → consistency over rephrasings from a white-box proxy; 5 citations |
| How is epistemic uncertainty estimated without retraining? | multi (2) | 10.1 s | gradient/perturbation methods, no retraining; 5 citations |
| What are the three components…? (Wang & Ji) | multi (3) | 3.3 s | all three components named correctly; cites p2 where they are introduced |
| What is the capital of France? (Wang & Ji) | — | 17.1 s | **refused** ("couldn't find the answer in the selected paper") |

No answer triggered the `uncited` or `invalid_citations_removed` flags in this run.

**Bugs and findings from testing**
- The first Gemini probe hung for minutes: the SDK has no default timeout. Added a request
  deadline. Google reports an expired deadline as HTTP 504, which the first version retried
  (up to 4 × 60 s per question); a test now ensures 504 fails fast instead.
- `gemini-2.5-flash` (the original default) returned 404 although still listed; it has been
  retired. Newer Flash models (3.5–3.8) returned 503 "high demand" or 504 repeatedly during
  development, while Flash-Lite answered in under a second to a few seconds.
- A typing check (mypy) caught that LangGraph identifies nodes by a parameter literally named
  `state`; fixed with a typed `Node` protocol.

**Limitations to discuss**
- **Dependence on a free hosted model:** availability of the stronger model was unreliable
  during development. The system degrades (Flash-Lite works; 503 with a clear message when
  nothing does), but answer quality varies with the model actually available. Report which
  model produced each evaluation result.
- **Citation checking verifies that a citation points to a real retrieved passage, not that
  the passage supports the claim.** Support was spot-checked by hand here; the perturbation
  inspector (next phase) and the evaluation address this more systematically.
- **Over-decomposition:** "What are the three components…?" was split into three nearly
  identical sub-questions (4 searches) though one search sufficed. Harmless but wasteful.
- **Citation numbers are not sequential** in the answer text (e.g. [8] before [1]); the UI
  can renumber for display.
- Answers can contain LaTeX math (e.g. `$\theta \in [0.2, 0.7]$`); the UI must render
  Markdown/math or show raw text.
- Single-turn only: no memory of previous questions.
- The refusal path still costs two model calls (classify, synthesize) when retrieval returns
  loosely related passages; keyword OR-matching means retrieval is rarely empty.

---

## Phase 4 — Streaming answers (branch `feat/streaming`)

**What was built** (see ADR 0005)
- `POST /documents/{doc_id}/ask/stream` sends the agent's progress and answer as
  **Server-Sent Events**: `status` when each step starts (classify, decompose, retrieve,
  synthesize), `sub_questions` once the question is decomposed, `token` for each piece of
  answer text, then `done` (the same citation-checked result as `/ask`) or `error`.
- One agent graph serves both endpoints: the synthesize node streams from Gemini and writes
  each piece to LangGraph's stream writer, which is a no-op when nobody is listening.
- **The final event is authoritative.** Citations can only be verified once the whole answer
  exists, so `done` carries the checked answer and the UI replaces the streamed text with it.
- **The `NOT_FOUND` signal is never streamed:** a small filter holds back the start of the
  answer while it could still be that code word, so a refusal shows only the friendly message.
- **Retry only before the first chunk:** a failure before any text is retried as before; a
  failure after text was sent ends the stream with an `error` event (retrying would repeat
  text the user already saw).
- A paper that doesn't exist is still a normal 404, because the check runs as a dependency
  before the stream starts; after that, failures can only be reported as `error` events.
- Built on FastAPI's built-in SSE support (keep-alive pings every 15 s); no new library.

**Results** (Docker, Gemini Flash-Lite for both tiers)

| Question (paper) | First progress | First answer text | Finished | Outcome |
|---|---|---|---|---|
| Which datasets were used, and why were they chosen? (MetaQA) | 1.2 s | 3.2 s | 3.5 s | 2 sub-questions shown at 2.6 s; 7 token events; 5 citations, no flags |
| What is the capital of France? (MetaQA) | 0.4 s | — | 2.0 s | refused; `NOT_FOUND` held back, 0 token events |
| Same datasets question with Flash 3.8 as answer model | 1.3 s | — | 63 s | Flash timed out; pings kept the connection open; ended with an `error` event |

Gemini streams sentence-sized pieces (about 10–20 words), not single words. With Flash-Lite
the whole answer takes about 0.5 s once it starts, so the clearest benefit for the user is the
step-by-step progress during the first 3 s, not the typing effect.

**Bugs and findings from testing**
- **Timeouts were never caught (bug from Phase 3, found by the real check).** google-genai 3.x
  makes requests with `httpx2`, whose `ReadTimeout` is not a subclass of `httpx`'s. The unit
  tests simulated an `httpx` timeout the SDK never raises, so they passed while the real
  timeout escaped: `/ask` would have returned 500 instead of 503, and the stream stopped
  without an `error` event. Fixed by catching `httpx2` timeouts (tests corrected first). The
  lesson for the report: a fake is only as good as its match to the real dependency.
- The stream route now also turns any unexpected error into a generic `error` event (details
  go to the server log), so a client never sees a stream simply stop.
- LangGraph's stream writer raises when a node is called outside a graph; injecting it as a
  `writer` parameter with a no-op default keeps nodes unit-testable on their own.

**Limitations to discuss**
- Streamed text is the raw model output; in the rare case a citation marker is removed by the
  checker, the visible answer changes slightly when `done` arrives.
- If the connection drops, the answer is lost: no resume (the `Last-Event-ID` mechanism is
  not used) and no server-side storage of answers.
- The browser's built-in `EventSource` only supports GET; the frontend must read the POST
  stream with `fetch`.

---

## Phase 5 — Frontend: dual-pane reader (branch `feat/frontend`)

**What was built** (see ADR 0006)
- A Next.js app: a home page to upload or pick a paper, and a paper page with the PDF on the
  left and the chat on the right. `docker compose up` now starts all three services
  (database, API, web app on port 3000).
- The chat shows each agent step as it happens ("Searching the paper…"), the sub-questions,
  the answer as it streams, then the citation-checked answer. Citation numbers become buttons;
  clicking one **scrolls the PDF to the page and highlights the cited passage** using the
  bounding boxes stored at ingestion. A Sources list under each answer gives the page of each
  citation and can expand to show the quoted passage. Refusals appear as a notice, errors as an
  alert, and audit flags (`uncited`, `invalid_citations_removed`) as warnings.
- Backend additions: `GET /documents/{doc_id}/file` serves the original PDF (404 if the paper
  or its file is missing), and CORS allows the frontend's origin (`CORS_ORIGINS`).
- 55 frontend tests (Vitest + React Testing Library): the SSE parser, the streaming client, the
  chat reducer, highlight geometry, and the components; plus 7 new backend tests.

**Results** (real browser, Docker stack, real Gemini)
- Home page lists the three sample papers; opening one renders the PDF.
- Datasets question on the MetaQA paper (Flash-Lite answer model): progress and sub-questions
  shown first, then a formatted answer with citation buttons [5], [8], [9] and a Sources list
  (pages 9, 10, 9). Clicking [8] scrolled to page 10 and highlighted the HotpotQA and FreshQA
  paragraphs and the dataset table, which are exactly the passage the claim relies on.
- "What is the capital of France?" showed the refusal notice.
- With Flash 3.8 as the answer model, the answer timed out after 60 s and the chat showed
  "The language model is busy…", then accepted a new question.
- No errors or warnings in the browser console.

**Bugs and findings from testing**
- **Line endings split across network chunks:** the first SSE parser turned a Windows line
  ending (`\r\n`) split
  between two chunks into a false event boundary. Found by reasoning about edge cases, pinned
  with a failing test, then fixed.
- Next 16 prerenders pages at build time; a page that reads the URL's paper id must sit in a
  `<Suspense>` boundary. The production build caught this (tests and type checks passed).
- Tooling versions had to match Node 20.18 (Vitest 4, jsdom 26); Node 20 is end-of-life, and
  the Docker image uses Node 24.

**Limitations to discuss**
- **Highlights include running headers/footers** when they were merged into the chunk (visible
  on page 10: the page footer is highlighted). This makes the Phase 1 cleaning limitation
  visible to users.
- The highlight marks the whole chunk (about 1,000 characters), not the specific sentence that
  supports the claim.
- All pages render at once; very long PDFs (100+ pages) would be slow to open.
- LaTeX in answers shows as raw text (no math rendering).
- Questions are single-turn; the chat history is only on screen and is lost on reload.
- No accounts: anyone who can reach the app sees all uploaded papers.
- **Deployment risk:** PDFs live on the backend's disk; free hosts may wipe it on restart, and
  then the viewer cannot load a paper even though questions still work.

## Phase 6 — Perturbation inspector (branch `feat/perturbation-inspector`)

**What was built** (see ADR 0007)
- `POST /documents/{doc_id}/diagnose` takes an answer from `/ask` and re-runs the answer step
  four times, changing one input each time: a **paraphrased** question, the passages in
  **reverse order**, an unrelated **distractor** passage from the same paper added, and the
  **most-cited passage dropped**. It compares each new answer with the original in two ways
  (embedding similarity and claim-by-claim agreement judged by Flash-Lite) and combines them
  into a 0-1 **uncertainty score** with a per-perturbation breakdown.
- `/ask` and the streaming `done` event now include `passage_ids`, the exact passages the
  model saw, so the inspector can rebuild the prompt.
- Pure, separately tested modules: `perturb.py` (the changes), `compare.py` (similarity,
  claim agreement), `score.py` (combining signals); `inspector.py` orchestrates them.
- 55 new backend tests (210 total), all with fake models except the database tests.

**Results** (real Gemini, Flash-Lite for answers and inspection, MetaQA paper)

| Question | Uncertainty | Time | What the breakdown showed |
|---|---|---|---|
| Which datasets were used to evaluate MetaQA? | 0.16 | 3.8 s | All claims agreed in every run; the score came only from embedding similarity (paraphrase 0.44 because of list formatting). Drop-cited risk 0.88: the datasets are listed in several passages. |
| What are the main limitations of MetaQA? | 0.06 | 7.9 s | Stable under every change; dropping the main passage lost one of three claims. |
| What temperature setting was used for the LLM calls? | 0.15 | 18.1 s | The distractor run **contradicted** a claim (it said SelfCheckGPT ran with temperature 0.5 by default, where the original said no explicit temperature). Dropping the main passage removed 3 of 4 claims, so drop-cited risk was low (0.21): the answer depended on its evidence. |

**Bugs and findings from testing**
- The two signals behave differently: claim agreement was 1.0 for every run of the datasets
  question, but embedding similarity fell to 0.44 just because one answer used a numbered
  list with bold names. Embedding similarity is sensitive to formatting, not only meaning.
- The drop-cited signal behaved as the ADR predicted: high risk when a fact is repeated across
  passages (datasets), low when the answer relies on one passage (temperature). This is why it
  is shown but not scored by default.
- Gemini's structured output accepted the judge's schema (a list of `agrees` / `contradicts` /
  `missing` verdicts per answer) without changes.

**Limitations to discuss**
- The score measures **consistency, not correctness**: an answer that is wrong in the same way
  every time scores as stable. It complements citations; it does not verify them.
- The judge is itself an LLM (Flash-Lite) and can mis-split claims or misjudge agreement.
- The similarity floor (0.7) and equal weights are untuned defaults; they need calibrating on
  the evaluation set.
- Perturbed answers use Flash-Lite even when the original came from Flash, so some
  disagreement may come from the model difference.
- Each inspection costs about six model calls, which matters on the free tier's daily quota.
- Only the answer step is perturbed; retrieval errors (wrong passages found) are not detected.

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
- Answer quality: Flash vs. Flash-Lite as the answer model; citation support rate (share of
  cited passages that actually support the claim, judged by hand).
- Refusal rate on out-of-scope questions vs. false refusals on answerable ones.
- Latency: time to first progress, first token, and full answer (streaming vs. `/ask`).
- Highlight precision: share of clicked citations whose highlighted passage visibly supports
  the claim (a small user-facing audit of citation quality).
- Inspector calibration: does uncertainty separate correct from incorrect answers (AUROC on the
  hand-labelled eval answers)? Tune the similarity floor and weights; test whether drop-cited
  adds signal.
- Inspector ablation: claim agreement only vs. embedding similarity only vs. both.
- Inspection cost: model calls, time, and tokens per answer.
