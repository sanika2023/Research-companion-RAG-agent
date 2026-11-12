import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

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
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
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
