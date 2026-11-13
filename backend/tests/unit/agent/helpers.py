import uuid

from app.retrieval.hybrid import SearchHit

DOC_ID = uuid.UUID(int=1)


def hit(text: str, page: int = 1) -> SearchHit:
    """A search hit whose id is derived from its text, so equal texts are the same chunk."""
    return SearchHit(
        chunk_id=uuid.uuid5(DOC_ID, text),
        doc_id=DOC_ID,
        page=page,
        chunk_index=0,
        text=text,
        char_start=0,
        char_end=len(text),
        bbox=[[0.0, 0.0, 1.0, 1.0]],
        score=0.0,
        keyword_rank=None,
        vector_rank=None,
    )


class FakeSearch:
    def __init__(self, results: dict[str, list[SearchHit]]) -> None:
        self.results = results
        self.queries: list[str] = []

    async def __call__(self, query: str) -> list[SearchHit]:
        self.queries.append(query)
        return self.results.get(query, [])
