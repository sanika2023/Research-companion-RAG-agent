# Paper RAG

Auditable research companion for academic papers: hybrid-search RAG with page-linked citations and a perturbation-based hallucination inspector.

This web app will make it easier for you to comprehend research papers and understand the big idea faster.

This uses a RAG system and references items in the given ground truth.

## Architecture


## Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- [uv](https://docs.astral.sh/uv/) for local backend development (installs Python 3.12 itself)
- A Gemini API key from Google AI Studio

## Setup
```bash
cp .env.example .env   # then fill in LLM_API_KEY
```
`.env` is gitignored; never commit it.

## Run with Docker (full stack)
```bash
docker compose up --build
```
- **The app: http://localhost:3000** (upload a paper, open it, ask questions)
- API health: http://localhost:8000/health
- Interactive API docs: http://localhost:8000/docs

The backend applies database migrations automatically on startup. Postgres is exposed on host
port **5433** (not 5432) to avoid clashing with a locally installed Postgres.

## Upload a paper
Use the **Try it out** button on `POST /documents` at http://localhost:8000/docs, or:
```bash
curl -F "file=@paper.pdf" http://localhost:8000/documents   # -> doc_id, page_count, chunk_count
curl http://localhost:8000/documents                        # list uploaded papers
```
Ingestion takes roughly 15–25 s per paper on a laptop CPU (embedding dominates). Original
PDFs are kept in the `uploads` Docker volume (or `backend/data/uploads/` when run locally).

## Ask a question about a paper
Needs `LLM_API_KEY` (a free Gemini API key from Google AI Studio) in `.env`.
```bash
curl -X POST http://localhost:8000/documents/<doc_id>/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which datasets were used to evaluate the method?"}'
```
The answer cites passages as `[n]`; each citation has its page, text, and bounding boxes.
`refused: true` means the paper doesn't answer the question. A `503` means Gemini is busy:
retry, or set `LLM_ANSWER_MODEL` to the Flash-Lite model.

To watch the answer arrive as it is written, use the streaming endpoint (`-N` turns off
curl's buffering):
```bash
curl -N -X POST http://localhost:8000/documents/<doc_id>/ask/stream   -H "Content-Type: application/json"   -d '{"question": "Which datasets were used to evaluate the method?"}'
```
It sends Server-Sent Events: `status` (each step as it starts), `sub_questions`, `token`
(answer text), then `done` (the checked answer with citations, same as `/ask`) or `error`.
Lines starting with `:` are keep-alive pings.

## Check an answer's hallucination risk
The perturbation inspector re-asks the question with one controlled change at a time and
measures how far the answer moves. Send back the question, the `answer`, and the
`passage_ids` from an `/ask` response (plus `sub_questions`, if any):
```bash
curl -X POST http://localhost:8000/documents/<doc_id>/diagnose   -H "Content-Type: application/json"   -d '{"question": "...", "answer": "...", "passage_ids": ["...", "..."]}'
```
`uncertainty` is 0 (stable) to 1 (unstable). `signals` gives a breakdown for each change:
`paraphrase` (reworded question), `reorder` (passages reversed), `distractor` (an unrelated
passage of the paper added), and `drop_cited` (the most-cited passage removed; shown but not
scored by default). Each has its `risk`, embedding `similarity`, `claim_agreement` with the
original's `claims`, and the perturbed answer itself. It makes about six Flash-Lite calls,
typically 5-20 seconds.

## Search a paper
Searches are scoped to one paper (hybrid keyword + vector search, fused with RRF):
```bash
curl -X POST http://localhost:8000/documents/<doc_id>/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Which datasets were used?", "top_k": 5}'
```
Each hit has the page, text, bounding boxes, and its `keyword_rank` / `vector_rank`.

## Using the app
1. On http://localhost:3000, upload a PDF (processing takes about 20 s) or pick an uploaded paper.
2. The paper opens with the PDF on the left and the chat on the right.
3. Ask a question. You see each step (understanding, searching, writing), then the answer streams in.
4. Click a citation number, or a source under the answer, to jump to that page with the cited
   passage highlighted. "Show passage" displays the quoted text.
5. To check an answer, click **Check this answer** under it. The question is re-asked with small
   changes (5-20 s, about six Flash-Lite calls), then a badge shows the hallucination risk
   (Low < 0.2, Medium < 0.4, High). Click the badge for the breakdown: each check's risk, the
   answer it produced, and the claims compared. The score measures consistency, not correctness.

## Run the frontend locally (hot reload)
Needs Node.js 20.18+ (24 LTS recommended) and the backend on port 8000.
```bash
cd frontend
npm install
npm run dev                      # http://localhost:3000
```
The browser calls the API directly, at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
This value is compiled into the browser code at **build time**: after changing it, rebuild
(`docker compose build frontend`). The backend only accepts browser requests from the origins in
`CORS_ORIGINS` (default `http://localhost:3000`).

## Run the backend locally (auto-reload)
```bash
docker compose up -d db          # database only
cd backend
uv sync                          # install dependencies
uv run alembic upgrade head      # create/update tables
uv run uvicorn app.main:app --reload
```

## Tests
```bash
cd backend
uv run pytest tests/unit         # fast, no database needed
uv run pytest                    # everything; integration tests need `docker compose up -d db`

cd frontend
npm test                         # Vitest + React Testing Library
npm run typecheck && npm run lint
```

## Stopping
```bash
docker compose down              # stop containers, keep data
docker compose down -v           # stop and DELETE the database and uploads volumes
```
Press `Ctrl+C` to stop a locally running `uvicorn`.

## Troubleshooting
- **The app says it can't reach the backend:** check http://localhost:8000/health. If the
  backend runs but the browser console shows a CORS error, add the page's origin to
  `CORS_ORIGINS` in `.env` and restart the backend.
- **The PDF pane says it couldn't load the PDF** although questions work: the original file is
  missing from storage (e.g. the `uploads` volume was deleted); upload the paper again.
- **`docker` not recognized:** restart VS Code / your terminal after installing Docker Desktop.
- **`invalid peer certificate: UnknownIssuer` from uv:** add `--system-certs` (e.g.
  `uv run --system-certs pytest`) so uv trusts the Windows certificate store.
- **`role "rag" does not exist` when running locally:** your `.env` points at port 5432 (a
  native Postgres). Docker's database is on **5433**; copy `DATABASE_URL` from `.env.example`.
- **`/ask` returns 404 from Gemini or always 503:** model names change; list the ones your
  key can use in Google AI Studio and update `LLM_ANSWER_MODEL` / `LLM_LIGHT_MODEL`.
- **`Psycopg cannot use the 'ProactorEventLoop'` on Windows:** run uvicorn with `--reload`
  (as above), which uses a compatible event loop. Docker (Linux) is unaffected.
- **Embedding model download fails with `CERTIFICATE_VERIFY_FAILED`** (local runs only; Docker
  bakes the model in): Python doesn't trust a TLS-intercepting proxy/antivirus. Download the
  model once into `backend/data/models/` using the Windows certificate store:
  ```bash
  cd backend
  uv run --system-certs --with truststore python -c "import truststore; truststore.inject_into_ssl(); from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='data/models')"
  ```
  If Python exits silently with `OPENSSL_Uplink ... no OPENSSL_Applink`, unset the
  `SSLKEYLOGFILE` environment variable for that command.

