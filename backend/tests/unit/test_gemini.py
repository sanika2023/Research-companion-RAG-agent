"""GeminiClient behaviour against a scripted stand-in for the google-genai SDK (no network)."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai import errors
from pydantic import BaseModel

from app.llm.gemini import GeminiClient, LLMUnavailableError


@dataclass
class Reply:
    text: str | None


class ScriptedModels:
    """Plays back outcomes in order: a string is a reply, an exception is raised."""

    def __init__(self, *outcomes: str | Exception | None) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> Reply:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return Reply(outcome)


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def make_client(models: ScriptedModels, sleeps: Sleeps | None = None) -> GeminiClient:
    sdk = SimpleNamespace(aio=SimpleNamespace(models=models))
    return GeminiClient(
        sdk,  # type: ignore[arg-type]  # duck-typed stand-in for genai.Client
        answer_model="answer-model",
        light_model="light-model",
        attempts=3,
        base_delay=1.0,
        sleep=sleeps or Sleeps(),
    )


def overloaded() -> errors.ServerError:
    return errors.ServerError(503, {"error": {"message": "high demand", "status": "UNAVAILABLE"}})


def rate_limited() -> errors.ClientError:
    return errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})


class Label(BaseModel):
    label: str


async def test_complete_uses_the_answer_model_by_default() -> None:
    models = ScriptedModels("hello")

    assert await make_client(models).complete("hi") == "hello"
    assert models.calls[0]["model"] == "answer-model"
    assert models.calls[0]["contents"] == "hi"


async def test_light_tier_uses_the_light_model() -> None:
    models = ScriptedModels("ok")

    await make_client(models).complete("hi", tier="light")

    assert models.calls[0]["model"] == "light-model"


async def test_complete_json_requests_schema_output_and_validates_it() -> None:
    models = ScriptedModels('{"label": "simple"}')

    result = await make_client(models).complete_json("classify", Label)

    assert result == Label(label="simple")
    config = models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is Label


@pytest.mark.parametrize("error", [overloaded(), rate_limited()])
async def test_transient_errors_are_retried_with_exponential_backoff(error: Exception) -> None:
    models, sleeps = ScriptedModels(error, error, "finally"), Sleeps()

    assert await make_client(models, sleeps).complete("hi") == "finally"
    assert sleeps.delays == [1.0, 2.0]


async def test_gives_up_after_the_last_attempt() -> None:
    models = ScriptedModels(overloaded(), overloaded(), overloaded())

    with pytest.raises(LLMUnavailableError):
        await make_client(models).complete("hi")
    assert len(models.calls) == 3


async def test_permanent_errors_are_not_retried() -> None:
    bad_request = errors.ClientError(400, {"error": {"message": "bad", "status": "INVALID"}})
    models = ScriptedModels(bad_request)

    with pytest.raises(errors.ClientError):
        await make_client(models).complete("hi")
    assert len(models.calls) == 1


async def test_timeout_is_reported_as_unavailable_without_retrying() -> None:
    models = ScriptedModels(httpx.ReadTimeout("slow"))

    with pytest.raises(LLMUnavailableError):
        await make_client(models).complete("hi")
    assert len(models.calls) == 1


async def test_server_side_deadline_is_a_timeout_and_not_retried() -> None:
    # The SDK sends our timeout as a deadline; Google answers 504 when it passes.
    deadline = errors.ServerError(504, {"error": {"message": "Deadline expired", "status": 504}})
    models = ScriptedModels(deadline)

    with pytest.raises(LLMUnavailableError):
        await make_client(models).complete("hi")
    assert len(models.calls) == 1


async def test_empty_reply_is_an_error() -> None:
    # Gemini returns no text when a reply is blocked (e.g. safety filters).
    with pytest.raises(LLMUnavailableError):
        await make_client(ScriptedModels(None)).complete("hi")
