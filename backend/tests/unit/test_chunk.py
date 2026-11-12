import pytest

from app.ingestion.chunk import chunk_pages
from app.ingestion.parse import ParsedPage, TextBlock

BOX_A = (10.0, 10.0, 100.0, 20.0)
BOX_B = (10.0, 30.0, 100.0, 40.0)


def page(number: int, *texts: str) -> ParsedPage:
    boxes = [(10.0, 10.0 * i, 100.0, 10.0 * i + 5) for i in range(len(texts))]
    return ParsedPage(number, [TextBlock(t, b) for t, b in zip(texts, boxes, strict=True)])


def test_short_page_becomes_one_chunk_with_page_and_offsets() -> None:
    [chunk] = chunk_pages([page(3, "Attention is all you need.")], size=100, overlap=10)

    assert chunk.page == 3
    assert chunk.text == "Attention is all you need."
    assert (chunk.char_start, chunk.char_end) == (0, len(chunk.text))


def test_chunks_never_span_two_pages() -> None:
    chunks = chunk_pages([page(1, "alpha beta"), page(2, "gamma delta")], size=100, overlap=10)

    assert [(c.page, c.text) for c in chunks] == [(1, "alpha beta"), (2, "gamma delta")]


def test_long_text_is_split_into_chunks_no_longer_than_size() -> None:
    words = " ".join(f"word{i}" for i in range(200))

    chunks = chunk_pages([page(1, words)], size=100, overlap=20)

    assert len(chunks) > 1
    assert all(len(c.text) <= 100 for c in chunks)


def test_consecutive_chunks_overlap() -> None:
    words = " ".join(f"word{i}" for i in range(200))

    first, second, *_ = chunk_pages([page(1, words)], size=100, overlap=20)

    assert second.char_start < first.char_end


def test_chunks_break_on_word_boundaries() -> None:
    words = " ".join(f"word{i}" for i in range(200))

    chunks = chunk_pages([page(1, words)], size=100, overlap=20)

    tokens = [token for c in chunks for token in c.text.split()]
    assert all(c.text == c.text.strip() for c in chunks)
    assert all(t.startswith("word") and t[4:].isdigit() for t in tokens)  # no split words


def test_chunk_offsets_slice_the_page_text_exactly() -> None:
    words = " ".join(f"word{i}" for i in range(200))
    page_text = words

    chunks = chunk_pages([page(1, words)], size=100, overlap=20)

    assert all(page_text[c.char_start : c.char_end] == c.text for c in chunks)


def test_chunk_bbox_lists_only_blocks_it_overlaps() -> None:
    p = ParsedPage(1, [TextBlock("a" * 60, BOX_A), TextBlock("b" * 60, BOX_B)])

    first, *rest = chunk_pages([p], size=50, overlap=0)

    assert first.bbox == [list(BOX_A)]
    assert list(BOX_B) in rest[-1].bbox


def test_chunk_indexes_are_sequential_across_the_document() -> None:
    chunks = chunk_pages([page(1, "one"), page(2, "two"), page(3, "three")], size=100, overlap=10)

    assert [c.chunk_index for c in chunks] == [0, 1, 2]


def test_pages_without_text_produce_no_chunks() -> None:
    assert chunk_pages([ParsedPage(1, [])], size=100, overlap=10) == []


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        chunk_pages([page(1, "text")], size=50, overlap=50)
