"""GeminiClient behaviour against a scripted stand-in for the google-genai SDK (no network)."""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from google.genai import errors
from pydantic import BaseModel

from app.llm.gemini import GeminiClient, LLMUnavailableError


@dataclass
class Reply:
    text: str | None


# One streamed call: raise on open (Exception), or yield chunks in order; an Exception
# inside the sequence is raised at that point in the stream.
StreamOutcome = Exception | Sequence[str | None | Exception]


class ScriptedModels:
    """Plays back outcomes in order: a string is a reply, an exception is raised."""

    def __init__(self, *outcomes: str | Exception | None) -> None:
        self.outcomes = list(outcomes)
        self.stream_outcomes: list[StreamOutcome] = []
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> Reply:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return Reply(outcome)

    async def generate_content_stream(self, **kwargs: Any) -> AsyncIterator[Reply]:
        self.calls.append(kwargs)
        outcome = self.stream_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return self._play(outcome)

    async def _play(self, chunks: Sequence[str | None | Exception]) -> AsyncIterator[Reply]:
        for chunk in chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield Reply(chunk)


def streaming(*outcomes: StreamOutcome) -> ScriptedModels:
    models = ScriptedModels()
    models.stream_outcomes = list(outcomes)
    return models


async def collect(chunks: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in chunks]


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
    models = ScriptedModels(httpx2.ReadTimeout("slow"))

    with pytest.raises(LLMUnavailableError):
        await make_client(models).complete("hi")
    assert len(models.calls) == 1


async def test_network_failure_is_reported_as_unavailable() -> None:
    # e.g. no internet, or a TLS-intercepting proxy failing certificate checks
    models = ScriptedModels(httpx2.ConnectError("certificate verify failed"))

    with pytest.raises(LLMUnavailableError):
        await make_client(models).complete("hi")


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


async def test_stream_yields_text_chunks_in_order_from_the_answer_model() -> None:
    models = streaming(["The ", "answer", " [1]."])

    assert await collect(make_client(models).stream("q")) == ["The ", "answer", " [1]."]
    assert models.calls[0]["model"] == "answer-model"


async def test_stream_skips_chunks_without_text() -> None:
    # The final chunk often carries only the finish reason, no text.
    models = streaming(["Hi", None, "!", None])

    assert await collect(make_client(models).stream("q")) == ["Hi", "!"]


async def test_stream_retries_when_opening_the_stream_fails() -> None:
    models, sleeps = streaming(overloaded(), ["ok"]), Sleeps()

    assert await collect(make_client(models, sleeps).stream("q")) == ["ok"]
    assert sleeps.delays == [1.0]


async def test_stream_retries_when_it_fails_before_the_first_chunk() -> None:
    models = streaming([rate_limited()], ["ok"])

    assert await collect(make_client(models).stream("q")) == ["ok"]


async def test_stream_failing_after_text_was_sent_is_unavailable_and_not_retried() -> None:
    # Retrying would repeat text the user has already seen.
    models = streaming(["partial", overloaded()], ["never used"])
    received: list[str] = []

    with pytest.raises(LLMUnavailableError):
        async for chunk in make_client(models).stream("q"):
            received.append(chunk)
    assert received == ["partial"]
    assert len(models.calls) == 1


async def test_stream_gives_up_after_the_last_attempt() -> None:
    models = streaming(overloaded(), overloaded(), overloaded())

    with pytest.raises(LLMUnavailableError):
        await collect(make_client(models).stream("q"))
    assert len(models.calls) == 3


async def test_stream_timeout_is_unavailable_without_retrying() -> None:
    models = streaming([httpx2.ReadTimeout("slow")])

    with pytest.raises(LLMUnavailableError):
        await collect(make_client(models).stream("q"))
    assert len(models.calls) == 1


async def test_stream_network_failure_is_reported_as_unavailable() -> None:
    models = streaming([httpx2.ConnectError("certificate verify failed")])

    with pytest.raises(LLMUnavailableError):
        await collect(make_client(models).stream("q"))


async def test_stream_with_no_text_at_all_is_an_error() -> None:
    with pytest.raises(LLMUnavailableError):
        await collect(make_client(streaming([None])).stream("q"))
