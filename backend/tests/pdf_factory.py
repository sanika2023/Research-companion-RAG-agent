from dataclasses import dataclass

import pymupdf


@dataclass(frozen=True)
class Text:
    x: float
    y: float
    text: str
    rotate: int = 0


def make_pdf(pages: list[list[Text]]) -> bytes:
    """Build an in-memory PDF; each inner list is one page's text items."""
    doc = pymupdf.open()
    for items in pages:
        page = doc.new_page(width=612, height=792)
        for item in items:
            page.insert_text((item.x, item.y), item.text, fontsize=11, rotate=item.rotate)
    data: bytes = doc.tobytes()
    doc.close()
    return data
