from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Repo-root .env locally; real env vars (Docker/hosting) override it.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str
    llm_api_key: SecretStr
    llm_answer_model: str
    llm_light_model: str
    embedding_model: str
    embedding_dim: int = 384
    langsmith_tracing: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # fields are populated from the environment
