import asyncio
from pathlib import Path

from fastembed import TextEmbedding


class FastEmbedEmbedder:
    """Local ONNX embedding model; satisfies the `Embedder` protocol."""

    def __init__(self, model_name: str, cache_dir: Path | None = None) -> None:
        # Loading reads ~130 MB from disk (downloading it the first time), so do it once.
        self._model = TextEmbedding(
            model_name=model_name, cache_dir=str(cache_dir) if cache_dir else None
        )
        self.dim: int = self._model.embedding_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Embedding is CPU-bound; a worker thread keeps the event loop serving other requests.
        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]
