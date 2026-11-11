from typing import Protocol


class LLMClient(Protocol):
    async def complete(self, prompt: str) -> str: ...


class Embedder(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
