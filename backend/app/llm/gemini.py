import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from app.llm.base import M, Tier

# 429 = free-tier rate limit; 500/503 = Google overloaded ("high demand") or a transient fault.
_RETRYABLE = {429, 500, 503}
# 504 = our timeout, sent to Google as a deadline, expired; treated like a client timeout.
_DEADLINE_EXCEEDED = 504


class LLMUnavailableError(RuntimeError):
    """The model couldn't produce a reply (overloaded, rate-limited, timed out, or blocked)."""


class GeminiClient:
    """`LLMClient` backed by the Gemini API, with retry and backoff for transient errors."""

    def __init__(
        self,
        sdk: genai.Client,
        *,
        answer_model: str,
        light_model: str,
        attempts: int = 4,
        base_delay: float = 2.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._sdk = sdk
        self._models: dict[Tier, str] = {"answer": answer_model, "light": light_model}
        self._attempts = attempts
        self._base_delay = base_delay
        self._sleep = sleep

    async def complete(self, prompt: str, *, tier: Tier = "answer") -> str:
        return await self._generate(prompt, tier, config=None)

    async def complete_json(self, prompt: str, schema: type[M], *, tier: Tier = "light") -> M:
        # Gemini's structured-output mode constrains the reply to the schema.
        config = types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=schema
        )
        return schema.model_validate_json(await self._generate(prompt, tier, config))

    async def _generate(self, prompt: str, tier: Tier, config: Any) -> str:
        for attempt in range(self._attempts):
            try:
                reply = await self._sdk.aio.models.generate_content(
                    model=self._models[tier], contents=prompt, config=config
                )
            except errors.APIError as exc:
                if exc.code == _DEADLINE_EXCEEDED:
                    raise LLMUnavailableError("Gemini request timed out") from exc
                if exc.code not in _RETRYABLE:
                    raise
                if attempt == self._attempts - 1:
                    raise LLMUnavailableError(f"Gemini unavailable: {exc}") from exc
                await self._sleep(self._base_delay * 2**attempt)
                continue
            except httpx.TimeoutException as exc:
                # Not retried: a timed-out request has already used the whole time budget.
                raise LLMUnavailableError("Gemini request timed out") from exc
            if not reply.text:
                raise LLMUnavailableError("Gemini returned no text (possibly blocked)")
            return reply.text
        raise AssertionError("unreachable")  # loop always returns or raises


def create_gemini_client(
    api_key: str, *, answer_model: str, light_model: str, timeout_s: float
) -> GeminiClient:
    sdk = genai.Client(
        api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
    )
    return GeminiClient(sdk, answer_model=answer_model, light_model=light_model)
