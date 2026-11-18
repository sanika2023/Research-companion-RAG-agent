from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.diagnostics.score import Perturbation


class Settings(BaseSettings):
    # Repo-root .env locally; real env vars (Docker/hosting) override it.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str
    llm_api_key: SecretStr
    llm_answer_model: str
    llm_light_model: str
    llm_timeout_s: float = Field(default=60, gt=0)
    embedding_model: str
    embedding_dim: int = 384
    embedding_cache_dir: Path = Path("data/models")
    langsmith_tracing: bool = False

    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=150, ge=0)
    max_upload_mb: int = Field(default=50, gt=0)
    upload_dir: Path = Path("data/uploads")

    retrieval_top_k: int = Field(default=8, gt=0)
    # How many hits each search (keyword, vector) contributes before fusion.
    retrieval_candidates: int = Field(default=40, gt=0)
    # 60 is the constant from the original RRF paper (Cormack et al., 2009).
    rrf_k: int = Field(default=60, gt=0)

    agent_max_sub_questions: int = Field(default=4, gt=0)
    # Passages shown to the answer model; more = more context but a longer, costlier prompt.
    agent_max_passages: int = Field(default=10, gt=0)

    # Cosine similarity at which two answers count as unrelated (bge puts most text pairs
    # above ~0.7); tune on the evaluation set.
    diagnostics_similarity_floor: float = Field(default=0.7, ge=0, lt=1)
    # 0 = shown in the breakdown but left out of the score, until evaluation shows whether
    # it predicts wrong answers (see ADR 0007).
    diagnostics_drop_cited_weight: float = Field(default=0.0, ge=0)
    # Model calls in flight at once per inspection; low to stay under free-tier rate limits.
    diagnostics_concurrency: int = Field(default=2, gt=0)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        # Fail at startup, not on the first request.
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.retrieval_top_k > self.retrieval_candidates:
            raise ValueError("RETRIEVAL_TOP_K must not exceed RETRIEVAL_CANDIDATES")
        return self

    @property
    def ingest(self) -> "IngestSettings":
        return IngestSettings(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            max_upload_mb=self.max_upload_mb,
            upload_dir=self.upload_dir,
        )

    @property
    def retrieval(self) -> "RetrievalSettings":
        return RetrievalSettings(
            top_k=self.retrieval_top_k, candidates=self.retrieval_candidates, rrf_k=self.rrf_k
        )

    @property
    def agent(self) -> "AgentSettings":
        return AgentSettings(
            max_sub_questions=self.agent_max_sub_questions, max_passages=self.agent_max_passages
        )

    @property
    def diagnostics(self) -> "DiagnosticsSettings":
        return DiagnosticsSettings(
            similarity_floor=self.diagnostics_similarity_floor,
            drop_cited_weight=self.diagnostics_drop_cited_weight,
            concurrency=self.diagnostics_concurrency,
        )


@dataclass(frozen=True)
class IngestSettings:
    """The slice of settings the upload path needs; easy to build in tests."""

    chunk_size: int
    chunk_overlap: int
    max_upload_mb: int
    upload_dir: Path


@dataclass(frozen=True)
class RetrievalSettings:
    top_k: int
    candidates: int
    rrf_k: int


@dataclass(frozen=True)
class AgentSettings:
    max_sub_questions: int
    max_passages: int


@dataclass(frozen=True)
class DiagnosticsSettings:
    similarity_floor: float
    drop_cited_weight: float
    concurrency: int

    @property
    def weights(self) -> dict[Perturbation, float]:
        return {
            "paraphrase": 1.0,
            "reorder": 1.0,
            "distractor": 1.0,
            "drop_cited": self.drop_cited_weight,
        }


class CorsSettings(BaseSettings):
    """Read separately so the app can be built without the database URL or API key."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # Comma-separated browser origins allowed to call the API: the frontend's URL(s).
    cors_origins: str = "http://localhost:3000"

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # fields are populated from the environment
