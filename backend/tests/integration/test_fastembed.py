import math

import pytest

from app.core.config import get_settings
from app.llm.embeddings import FastEmbedEmbedder

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def embedder() -> FastEmbedEmbedder:
    settings = get_settings()
    return FastEmbedEmbedder(settings.embedding_model, cache_dir=settings.embedding_cache_dir)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


async def test_embeddings_have_the_schema_dimension(embedder: FastEmbedEmbedder) -> None:
    vectors = await embedder.embed(["attention mechanisms", "graph neural networks"])

    assert embedder.dim == 384
    assert [len(v) for v in vectors] == [384, 384]


async def test_related_texts_are_closer_than_unrelated(embedder: FastEmbedEmbedder) -> None:
    query, related, unrelated = await embedder.embed(
        [
            "How do language models hallucinate?",
            "LLMs sometimes generate fluent but false statements.",
            "The recipe calls for two cups of flour.",
        ]
    )

    assert cosine(query, related) > cosine(query, unrelated)


async def test_empty_input_returns_no_vectors(embedder: FastEmbedEmbedder) -> None:
    assert await embedder.embed([]) == []
