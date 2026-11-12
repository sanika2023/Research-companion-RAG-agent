import pytest

from app.ingestion.parse import InvalidPDFError, parse_pdf
from tests.pdf_factory import Text, make_pdf


def test_parse_numbers_pages_from_one() -> None:
    pdf = make_pdf([[Text(72, 72, "first page")], [Text(72, 72, "second page")]])

    doc = parse_pdf(pdf)

    assert doc.page_count == 2
    assert [p.number for p in doc.pages] == [1, 2]


def test_parse_extracts_block_text_with_its_bounding_box() -> None:
    doc = parse_pdf(make_pdf([[Text(100, 200, "Transformers use attention")]]))

    [block] = doc.pages[0].blocks
    x0, y0, x1, y1 = block.bbox
    assert block.text == "Transformers use attention"
    assert x0 <= 100 <= x1 and y0 <= 200 <= y1


def test_parse_ignores_rotated_text_like_arxiv_watermarks() -> None:
    pdf = make_pdf([[Text(72, 72, "body text"), Text(30, 500, "arXiv:2404.10193v1", rotate=90)]])

    texts = [b.text for b in parse_pdf(pdf).pages[0].blocks]

    assert texts == ["body text"]


def test_parse_drops_blocks_that_are_only_page_numbers() -> None:
    pdf = make_pdf([[Text(72, 72, "body text"), Text(300, 750, "12")]])

    texts = [b.text for b in parse_pdf(pdf).pages[0].blocks]

    assert texts == ["body text"]


def test_parse_rejoins_words_hyphenated_across_lines() -> None:
    pdf = make_pdf([[Text(72, 72, "synonymous and syn-"), Text(72, 85, "onymous mutations")]])

    [block] = parse_pdf(pdf).pages[0].blocks

    assert block.text == "synonymous and synonymous mutations"


def test_parse_keeps_pages_without_text_as_empty() -> None:
    doc = parse_pdf(make_pdf([[Text(72, 72, "text")], []]))

    assert doc.page_count == 2
    assert doc.pages[1].blocks == []


def test_parse_rejects_bytes_that_are_not_a_pdf() -> None:
    with pytest.raises(InvalidPDFError):
        parse_pdf(b"definitely not a pdf")
