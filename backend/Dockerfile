FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so this layer is cached until pyproject/uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Bake the embedding model into the image so the first upload doesn't wait on a download.
# Must match EMBEDDING_MODEL at runtime; the path matches the EMBEDDING_CACHE_DIR default.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RUN .venv/bin/python -c "from fastembed import TextEmbedding; \
TextEmbedding('${EMBEDDING_MODEL}', cache_dir='data/models')"

COPY alembic.ini ./
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Migrate on boot so a fresh database is ready without manual steps.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
