from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.models import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    # Tests inject a URL; otherwise use the app's settings.
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
