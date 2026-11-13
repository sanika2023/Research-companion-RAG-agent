import asyncio
import hashlib
import math
import random
import sys

import pytest

from app.llm.base import M, Tier

if sys.platform == "win32":  # psycopg's async mode can't use Windows' default Proactor loop
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class FakeLLM:
    """Returns a canned reply for the first keyword found in the prompt; records every call."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = responses or {}
        self.prompts: list[str] = []
        self.tiers: list[Tier] = []

    async def complete(self, prompt: str, *, tier: Tier = "answer") -> str:
        self._record(prompt, tier)
        return self._match(prompt) or "fake answer"

    async def complete_json(self, prompt: str, schema: type[M], *, tier: Tier = "light") -> M:
        self._record(prompt, tier)
        reply = self._match(prompt)
        if reply is None:
            raise ValueError(f"FakeLLM has no JSON reply for prompt: {prompt[:80]!r}")
        return schema.model_validate_json(reply)

    def _record(self, prompt: str, tier: Tier) -> None:
        self.prompts.append(prompt)
        self.tiers.append(tier)

    def _match(self, prompt: str) -> str | None:
        return next((reply for key, reply in self.responses.items() if key in prompt), None)


class FakeEmbedder:
    """Hash-seeded unit vectors: same text always maps to the same vector, no model needed."""

    dim = 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
        rng = random.Random(seed)
        raw = [rng.gauss(0, 1) for _ in range(self.dim)]
        norm = math.sqrt(sum(x * x for x in raw))
        return [x / norm for x in raw]


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()
