# CLAUDE.md — Paper RAG (Honors Thesis)

An auditable research companion: users upload academic PDFs, an agent decomposes
multi-step questions, retrieves chunks via hybrid search, and answers with
page-linked citations. A perturbation inspector scores each answer's
hallucination risk before it is shown.

Deliverables: deployed web app + `docker compose up` local install + 20–30 query
evaluation + thesis report + demo video. **Target: done by Nov 30, 2026.**

## Stack
- **Frontend:** Next.js (App Router) + React + TypeScript + Tailwind. Dual pane: PDF viewer | chat with streaming tokens and expandable citations.
- **Backend:** FastAPI (async) + LangGraph agent. Python 3.11+, managed with `uv`.
- **DB/Search:** PostgreSQL + pgvector. Hybrid search = BM25/full-text (`tsvector`) + dense vectors, fused with Reciprocal Rank Fusion.
- **Tools:** FastMCP server exposing `summarize`, `translate`, `retrieve`.
- **Observability:** LangSmith tracing (off in tests).
- **Infra:** docker-compose (db, backend, frontend).

## Commands
```bash
docker compose up -d db                 # start Postgres + pgvector
cd backend && uv sync                   # install backend deps
cd backend && uv run pytest             # all backend tests
cd backend && uv run pytest tests/unit  # fast tests only
cd backend && uv run ruff check . && uv run ruff format . && uv run mypy app
cd backend && uv run uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
cd frontend && npm test                 # vitest
docker compose up --build               # full stack
```
Keep this section updated when commands change.

## Repo map
- `backend/app/api/routes/` — HTTP endpoints only; no business logic
- `backend/app/ingestion/` — PDF parse → chunk (with page numbers + bbox) → embed → store
- `backend/app/retrieval/` — lexical, vector, and fused hybrid search
- `backend/app/agent/` — LangGraph graph; one file per node in `nodes/`
- `backend/app/diagnostics/` — perturbation generation, answer comparison, uncertainty score
- `backend/app/llm/` — provider-agnostic LLM + embedding clients (the only place that calls a model API)
- `backend/app/schemas/` — Pydantic request/response models
- `mcp_server/` — FastMCP tools wrapping backend services
- `frontend/src/components/` — `pdf-viewer`, `chat`, `citations`, `diagnostics`
- `eval/` — test queries, run scripts, results
- `docs/decisions/` — short ADRs for non-obvious choices (feeds the thesis report)

## Rules

### Test-driven development (required)
1. **Red:** write a failing test for the behavior first. Run it and confirm it fails for the right reason.
2. **Green:** write the minimum code to pass.
3. **Refactor:** clean up with tests green.
- Never edit or delete a test just to make it pass. If a test is wrong, say so and explain before changing it.
- Never call real LLM/embedding APIs in unit tests. Use the fakes in `tests/conftest.py` (deterministic `FakeLLM`, `FakeEmbedder`).
- Integration tests (`tests/integration/`) may use the real Postgres container; mark them `@pytest.mark.integration`.
- Test behavior, not implementation details. One concept per test; descriptive names (`test_hybrid_search_ranks_exact_term_match_first`).
- Frontend: vitest + React Testing Library for components and hooks.

### Code style
- **Comments are concise.** Explain *why*, not *what*. No comments that restate the code. Docstrings: one line unless the function is genuinely non-obvious.
- Type hints on all Python functions; strict TypeScript, no `any`.
- Small, single-purpose functions and modules. Prefer pure functions in `retrieval/` and `diagnostics/` so they are easy to test.
- Async all the way in FastAPI paths; no blocking I/O in request handlers.
- Pydantic models at every API boundary.
- Config via environment variables (`app/core/config.py`); never hardcode keys, URLs, or model names.

### Workflow
- For anything bigger than a small change, propose a short plan first and wait for my OK.
- Work in small increments; run the relevant tests after each change.
- Ask before adding a new dependency, and say why it's needed.
- Don't touch files unrelated to the current task.
- Commits: small, Conventional Commits style (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`). Don't commit unless I ask.
- Never commit `.env`, API keys, or uploaded PDFs.
- If something is ambiguous, ask instead of guessing. If you find a bug outside the task, flag it, don't silently fix it.
- When a non-obvious design decision is made, add a short ADR in `docs/decisions/` (context, decision, alternatives).

## Key design notes
- **Chunks keep provenance:** `doc_id`, `page`, `chunk_index`, char offsets/bbox. Citations must link back to an exact page in the viewer.
- **Answers must cite:** every claim in a final answer maps to ≥1 retrieved chunk id; the agent refuses or flags when retrieval is empty.
- **Agent graph (initial):** `classify → decompose (if multi-step) → retrieve → (tool call?) → synthesize → diagnose → respond`.
- **Perturbation inspector:** run the question through N perturbations (paraphrase, reorder context, drop top chunk, distractor chunk), compare answers against the original (embedding similarity + claim-level agreement), combine into a 0–1 uncertainty score with per-signal breakdown. Runs as a background task; UI shows it in a diagnostics drawer.
- **Streaming:** Server-Sent Events from FastAPI to the chat pane.

## Plan (compressed to Nov 30)
| Dates | Phase | Done when |
|---|---|---|
| Nov 11–16 | 1. Ingestion & retrieval | Upload a PDF via API, hybrid search returns page-tagged chunks; tests green |
| Nov 17–22 | 2. Agent & core UI | Ask a question in the UI, get a streamed, cited answer; clicking a citation jumps to the page |
| Nov 23–26 | 3. Perturbation diagnostics | Uncertainty score + breakdown shown in the drawer |
| Nov 27–30 | 4. Eval, deploy, write-up | 20–30 queries evaluated, deployed, report drafted, demo recorded |

**Scope priority** (cut from the bottom if behind): hybrid search + citations → streaming chat UI → perturbation score → summary tool → MCP server → translation tool → LangSmith eval dashboards.

## Open decisions -- proposed
- LLM provider/model: Google Gemini API (free tier). Flash for answers, Flash-Lite for perturbation runs. Model names via env vars. Retry with backoff on 429.
- Embedding model + dimension: BAAI/bge-small-en-v1.5 via sentence-transformers, 384-dim, runs locally
- PDF parser: PyMuPDF (page numbers + bounding boxes for citations)
- Deployment target: ___
