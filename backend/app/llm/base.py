from collections.abc import AsyncIterator
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

# "answer" = the stronger model for final answers; "light" = the cheaper model for routing
# steps and perturbation runs. Which concrete models these are comes from config.
Tier = Literal["answer", "light"]

M = TypeVar("M", bound=BaseModel)


class LLMClient(Protocol):
    async def complete(self, prompt: str, *, tier: Tier = "answer") -> str: ...

    async def complete_json(self, prompt: str, schema: type[M], *, tier: Tier = "light") -> M:
        """Return the model's reply parsed and validated as `schema`."""
        ...

    def stream(self, prompt: str, *, tier: Tier = "answer") -> AsyncIterator[str]:
        """Yield the reply as it is generated, in chunks of text."""
        ...


class Embedder(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
