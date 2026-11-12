from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
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
    embedding_cache_dir: Path = Path("data/models")
    langsmith_tracing: bool = False

    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=150, ge=0)
    max_upload_mb: int = Field(default=50, gt=0)
    upload_dir: Path = Path("data/uploads")

    @model_validator(mode="after")
    def _overlap_fits_in_chunk(self) -> Self:
        # Fail at startup, not on the first upload.
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return self

    @property
    def ingest(self) -> "IngestSettings":
        return IngestSettings(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            max_upload_mb=self.max_upload_mb,
            upload_dir=self.upload_dir,
        )


@dataclass(frozen=True)
class IngestSettings:
    """The slice of settings the upload path needs; easy to build in tests."""

    chunk_size: int
    chunk_overlap: int
    max_upload_mb: int
    upload_dir: Path


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # fields are populated from the environment
