from collections.abc import Iterator
from dataclasses import dataclass

from app.ingestion.parse import BBox, ParsedPage


@dataclass(frozen=True)
class Chunk:
    page: int
    chunk_index: int
    text: str
    # Offsets into the page text (the page's blocks joined with "\n").
    char_start: int
    char_end: int
    bbox: list[list[float]]


def chunk_pages(pages: list[ParsedPage], size: int, overlap: int) -> list[Chunk]:
    """Split each page into overlapping word-aligned windows; chunks never cross pages."""
    if not 0 <= overlap < size:
        raise ValueError("overlap must be >= 0 and smaller than size")
    chunks: list[Chunk] = []
    for page in pages:
        text, spans = _page_text(page)
        for start, end in _windows(text, size, overlap):
            chunks.append(
                Chunk(
                    page=page.number,
                    chunk_index=len(chunks),
                    text=text[start:end],
                    char_start=start,
                    char_end=end,
                    bbox=[list(box) for box, (s, e) in spans if s < end and e > start],
                )
            )
    return chunks


def _page_text(page: ParsedPage) -> tuple[str, list[tuple[BBox, tuple[int, int]]]]:
    parts: list[str] = []
    spans: list[tuple[BBox, tuple[int, int]]] = []
    offset = 0
    for block in page.blocks:
        spans.append((block.bbox, (offset, offset + len(block.text))))
        parts.append(block.text)
        offset += len(block.text) + 1  # "\n" separator
    return "\n".join(parts), spans


def _windows(text: str, size: int, overlap: int) -> Iterator[tuple[int, int]]:
    n = len(text)
    start = _skip_space(text, 0)
    while start < n:
        end = min(start + size, n)
        hard_cut = False
        if end < n and not text[end].isspace():
            cut = _last_space(text, start, end)
            if cut > start:
                end = cut
            else:
                hard_cut = True  # a single "word" longer than size
        reached_end = end == n
        while end > start and text[end - 1].isspace():
            end -= 1
        yield start, end
        if reached_end:
            return

        if hard_cut or end - overlap <= start:
            nxt = end  # no overlap: re-aligning here would skip unseen characters
        else:
            nxt = end - overlap
            if not text[nxt - 1].isspace():
                nxt = _next_space(text, nxt, end)  # don't start mid-word
        start = _skip_space(text, nxt)


def _skip_space(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _last_space(text: str, start: int, end: int) -> int:
    for i in range(end - 1, start, -1):
        if text[i].isspace():
            return i
    return start


def _next_space(text: str, i: int, limit: int) -> int:
    while i < limit and not text[i].isspace():
        i += 1
    return i
