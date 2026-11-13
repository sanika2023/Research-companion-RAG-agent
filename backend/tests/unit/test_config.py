import pytest
from pydantic import ValidationError

from app.core.config import Settings

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+psycopg://u:p@host:5432/db",
    "LLM_API_KEY": "super-secret-key",
    "LLM_ANSWER_MODEL": "answer-model",
    "LLM_LIGHT_MODEL": "light-model",
    "EMBEDDING_MODEL": "embed-model",
}


def load_settings() -> Settings:
    """Ignore any real .env so tests only see monkeypatched variables."""
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def test_settings_are_read_from_environment(env: pytest.MonkeyPatch) -> None:
    settings = load_settings()

    assert settings.database_url == REQUIRED_ENV["DATABASE_URL"]
    assert settings.llm_answer_model == "answer-model"
    assert settings.llm_light_model == "light-model"
    assert settings.embedding_model == "embed-model"


def test_missing_database_url_fails_at_startup(env: pytest.MonkeyPatch) -> None:
    env.delenv("DATABASE_URL")

    with pytest.raises(ValidationError):
        load_settings()


def test_api_key_is_not_leaked_in_repr(env: pytest.MonkeyPatch) -> None:
    settings = load_settings()

    assert "super-secret-key" not in repr(settings)
    assert settings.llm_api_key.get_secret_value() == "super-secret-key"


def test_langsmith_tracing_is_off_by_default(env: pytest.MonkeyPatch) -> None:
    assert load_settings().langsmith_tracing is False


def test_ingestion_defaults(env: pytest.MonkeyPatch) -> None:
    settings = load_settings()

    assert (settings.chunk_size, settings.chunk_overlap) == (1000, 150)
    assert settings.max_upload_mb == 50


def test_chunking_is_tunable_from_environment(env: pytest.MonkeyPatch) -> None:
    env.setenv("CHUNK_SIZE", "500")
    env.setenv("CHUNK_OVERLAP", "50")

    settings = load_settings()

    assert (settings.chunk_size, settings.chunk_overlap) == (500, 50)


def test_overlap_not_smaller_than_size_fails_at_startup(env: pytest.MonkeyPatch) -> None:
    env.setenv("CHUNK_SIZE", "100")
    env.setenv("CHUNK_OVERLAP", "100")

    with pytest.raises(ValidationError):
        load_settings()


def test_retrieval_defaults(env: pytest.MonkeyPatch) -> None:
    retrieval = load_settings().retrieval

    assert (retrieval.top_k, retrieval.candidates, retrieval.rrf_k) == (8, 40, 60)


def test_top_k_larger_than_candidates_fails_at_startup(env: pytest.MonkeyPatch) -> None:
    env.setenv("RETRIEVAL_TOP_K", "50")
    env.setenv("RETRIEVAL_CANDIDATES", "40")

    with pytest.raises(ValidationError):
        load_settings()


def test_agent_defaults(env: pytest.MonkeyPatch) -> None:
    settings = load_settings()

    assert settings.llm_timeout_s == 60
    assert (settings.agent.max_sub_questions, settings.agent.max_passages) == (4, 10)
