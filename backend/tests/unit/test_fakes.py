import math

from tests.conftest import FakeEmbedder, FakeLLM


async def test_fake_embedder_is_deterministic() -> None:
    embedder = FakeEmbedder()

    first, second = (
        await embedder.embed(["attention is all you need"]),
        await embedder.embed(["attention is all you need"]),
    )

    assert first == second


async def test_fake_embedder_gives_different_texts_different_vectors() -> None:
    a, b = await FakeEmbedder().embed(["transformers", "protein folding"])

    assert a != b


async def test_fake_embedder_returns_unit_vectors_of_declared_dimension() -> None:
    embedder = FakeEmbedder()

    [vector] = await embedder.embed(["hello"])

    assert len(vector) == embedder.dim == 384
    assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-9)


async def test_fake_llm_returns_canned_response_and_records_prompts() -> None:
    llm = FakeLLM(responses={"summarize": "short summary"})

    answer = await llm.complete("please summarize this")

    assert answer == "short summary"
    assert llm.prompts == ["please summarize this"]


async def test_fake_llm_falls_back_to_default_answer() -> None:
    assert await FakeLLM().complete("anything") == "fake answer"
