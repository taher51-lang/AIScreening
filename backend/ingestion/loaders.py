"""
PDF loading via PyMuPDF (fitz), chosen over pypdf-based loaders because
these are dense academic textbooks (multi-column layout in places, math
notation, headers/footers) where PyMuPDF's text-ordering is more reliable.

Section-title detection: PyMuPDF exposes per-span font size via
page.get_text("dict"). We treat any text span with a font size notably
larger than the page's median (body-text) font size as a heading
candidate. This is a heuristic, not a guarantee -- textbooks vary in
formatting -- but it's cheap and good enough to attach a `section_title`
to each chunk's metadata for traceability.
"""

import statistics
from dataclasses import dataclass
from typing import Iterator

import fitz  # PyMuPDF


@dataclass
class PageContent:
    page_number: int          # 1-indexed, human-readable
    text: str                 # full plain text of the page
    section_title: str | None  # best-guess current section heading


def _median_font_size(page_dict: dict) -> float:
    sizes = [
        span["size"]
        for block in page_dict.get("blocks", [])
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        if span.get("text", "").strip()
    ]
    return statistics.median(sizes) if sizes else 10.0


def _detect_heading(page_dict: dict, median_size: float) -> str | None:
    """Return the largest heading-like span on the page, if any."""
    candidates = []
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                # Heading heuristic: notably larger than body text, short line
                # (headings are rarely full paragraphs), not just a page number.
                if span["size"] >= median_size * 1.25 and len(text) < 120 and not text.isdigit():
                    candidates.append((span["size"], text))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


def iter_pdf_pages(pdf_path: str) -> Iterator[PageContent]:
    """
    Yield PageContent one page at a time instead of materializing the whole
    book in memory -- important since these are full-length textbooks
    (hundreds of pages each) and we run ingestion across 6-7 of them in
    one process.

    `doc` stays open for the lifetime of the generator; callers should
    fully consume it (e.g. via a for-loop) so `doc.close()` in the
    `finally` block runs deterministically.
    """
    doc = fitz.open(pdf_path)
    last_known_section: str | None = None

    try:
        for i, page in enumerate(doc):
            page_dict = page.get_text("dict")
            median_size = _median_font_size(page_dict)
            heading = _detect_heading(page_dict, median_size)

            if heading:
                last_known_section = heading

            text = page.get_text("text")
            yield PageContent(
                page_number=i + 1,
                text=text,
                section_title=last_known_section,
            )
    finally:
        doc.close()