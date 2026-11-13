import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import (
    get_agent_settings,
    get_embedder,
    get_ingest_settings,
    get_llm,
    get_retrieval_settings,
)
from app.core.config import AgentSettings, IngestSettings, RetrievalSettings
from app.db.session import get_session
from app.main import app
from tests.conftest import FakeEmbedder, FakeLLM

BACKEND_DIR = Path(__file__).resolve().parents[2]
ADMIN_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", "postgresql+psycopg://rag:rag@localhost:5433/postgres"
)
TEST_DB = "rag_test"
TEST_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}"


def _alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "app" / "db" / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture(scope="session")
def migrated_db_url() -> Iterator[str]:
    """A fresh database built purely by running the migrations."""
    # Short timeout so a stopped container skips fast instead of hanging for minutes.
    admin = create_engine(
        ADMIN_URL, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3}
    )
    try:
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
            conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    except OperationalError:
        pytest.skip("Postgres not reachable; start it with `docker compose up -d db`")
    command.upgrade(_alembic_config(TEST_URL), "head")
    yield TEST_URL
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
    admin.dispose()


@pytest.fixture
def sync_engine(migrated_db_url: str) -> Iterator[Engine]:
    engine = create_engine(migrated_db_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE documents CASCADE"))
    yield engine
    engine.dispose()


@pytest.fixture
async def async_engine(migrated_db_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_db_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(
    sync_engine: Engine, async_engine: AsyncEngine, tmp_path: Path
) -> AsyncIterator[AsyncClient]:
    """The real app wired to the test database, the fake embedder, and a temp upload dir."""

    async def test_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(async_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_ingest_settings] = lambda: IngestSettings(
        chunk_size=1000, chunk_overlap=150, max_upload_mb=1, upload_dir=tmp_path
    )
    app.dependency_overrides[get_retrieval_settings] = lambda: RetrievalSettings(
        top_k=8, candidates=40, rrf_k=60
    )
    app.dependency_overrides[get_agent_settings] = lambda: AgentSettings(
        max_sub_questions=4, max_passages=10
    )
    app.dependency_overrides[get_llm] = FakeLLM  # never a real model in tests
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
