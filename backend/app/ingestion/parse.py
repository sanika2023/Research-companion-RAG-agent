import re
from dataclasses import dataclass
from typing import Any

import pymupdf

BBox = tuple[float, float, float, float]


class InvalidPDFError(ValueError):
    pass


@dataclass(frozen=True)
class TextBlock:
    text: str
    bbox: BBox


@dataclass(frozen=True)
class ParsedPage:
    number: int  # 1-based, matches the PDF viewer
    blocks: list[TextBlock]


@dataclass(frozen=True)
class ParsedDocument:
    page_count: int
    pages: list[ParsedPage]


def parse_pdf(data: bytes) -> ParsedDocument:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError) as exc:
        raise InvalidPDFError("not a readable PDF") from exc
    with doc:
        pages = [
            ParsedPage(number=i + 1, blocks=_extract_blocks(page)) for i, page in enumerate(doc)
        ]
    return ParsedDocument(page_count=len(pages), pages=pages)


def _extract_blocks(page: pymupdf.Page) -> list[TextBlock]:
    raw = page.get_text("dict", flags=pymupdf.TEXT_DEHYPHENATE)
    blocks = []
    for block in raw["blocks"]:
        if block["type"] != 0:  # 0 = text; skip images
            continue
        text = _horizontal_text(block)
        if text and not text.isdigit():  # bare digits are page numbers / figure markers
            blocks.append(TextBlock(text=text, bbox=tuple(block["bbox"])))
    return blocks


def _horizontal_text(block: dict[str, Any]) -> str:
    # Rotated lines are margin watermarks (e.g. arXiv IDs), not body text.
    lines = [
        "".join(span["text"] for span in line["spans"])
        for line in block["lines"]
        if line["dir"] == (1.0, 0.0)
    ]
    return re.sub(r"\s+", " ", _join_lines(lines)).strip()


def _join_lines(lines: list[str]) -> str:
    # "syn-" + "onymous" -> "synonymous"; keeps "Fig. 3-" + "B" style breaks intact.
    out = ""
    for line in lines:
        line = line.strip()
        if out.endswith("-") and line[:1].islower():
            out = out[:-1] + line
        else:
            out = f"{out} {line}" if out else line
    return out
