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
```

## Stopping
```bash
docker compose down              # stop containers, keep data
docker compose down -v           # stop and DELETE the database and uploads volumes
```
Press `Ctrl+C` to stop a locally running `uvicorn`.

## Troubleshooting
- **`docker` not recognized:** restart VS Code / your terminal after installing Docker Desktop.
- **`invalid peer certificate: UnknownIssuer` from uv:** add `--system-certs` (e.g.
  `uv run --system-certs pytest`) so uv trusts the Windows certificate store.
- **Embedding model download fails with `CERTIFICATE_VERIFY_FAILED`** (local runs only; Docker
  bakes the model in): Python doesn't trust a TLS-intercepting proxy/antivirus. Download the
  model once into `backend/data/models/` using the Windows certificate store:
  ```bash
  cd backend
  uv run --system-certs --with truststore python -c "import truststore; truststore.inject_into_ssl(); from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='data/models')"
  ```
  If Python exits silently with `OPENSSL_Uplink ... no OPENSSL_Applink`, unset the
  `SSLKEYLOGFILE` environment variable for that command.

