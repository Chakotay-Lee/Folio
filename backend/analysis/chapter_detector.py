"""Chapter boundary detection: TOC → heading heuristic → fixed-page fallback."""
from __future__ import annotations
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chapter:
    index: int          # 1-based
    title: str
    start_page: int     # 0-based
    end_page: int       # exclusive


def detect_chapters(pdf_path: Path, fixed_chunk_size: int = 20) -> list[Chapter]:
    """Return chapter list using priority: TOC → headings → fixed chunks."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return _fixed_chunks(0, fixed_chunk_size)

    doc = fitz.open(str(pdf_path))
    total = doc.page_count

    chapters = _from_toc(doc)
    if len(chapters) >= 2:
        doc.close()
        return chapters

    chapters = _from_headings(doc)
    if len(chapters) >= 2:
        doc.close()
        return chapters

    doc.close()
    return _fixed_chunks(total, fixed_chunk_size)


def _from_toc(doc) -> list[Chapter]:
    toc = doc.get_toc()  # [[level, title, page], ...]
    if not toc:
        return []

    # Use only top-level entries (level == 1) as chapter boundaries
    top = [(title, page - 1) for level, title, page in toc if level == 1]
    if len(top) < 2:
        return []

    chapters = []
    for i, (title, start) in enumerate(top):
        end = top[i + 1][1] if i + 1 < len(top) else doc.page_count
        chapters.append(Chapter(index=i + 1, title=title, start_page=start, end_page=end))
    return chapters


def _from_headings(doc) -> list[Chapter]:
    """Detect pages that start with large/bold text as chapter openers."""
    boundaries: list[tuple[int, str]] = []

    for page_num in range(doc.page_count):
        page = doc[page_num]
        blocks = page.get_text("dict", flags=0)["blocks"]
        for block in blocks:
            if block.get("type") != 0:  # text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size", 0)
                    flags = span.get("flags", 0)
                    is_bold = bool(flags & 16)
                    text = span.get("text", "").strip()
                    if text and (size >= 14 or is_bold):
                        boundaries.append((page_num, text[:80]))
                        break
                else:
                    continue
                break
            else:
                continue
            break

    if len(boundaries) < 2:
        return []

    chapters = []
    for i, (start, title) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else doc.page_count
        chapters.append(Chapter(index=i + 1, title=title, start_page=start, end_page=end))
    return chapters


def _fixed_chunks(total_pages: int, chunk_size: int) -> list[Chapter]:
    if total_pages == 0:
        return [Chapter(index=1, title="Section 1", start_page=0, end_page=0)]
    n = math.ceil(total_pages / chunk_size)
    chapters = []
    for i in range(n):
        start = i * chunk_size
        end = min(start + chunk_size, total_pages)
        chapters.append(Chapter(index=i + 1, title=f"Section {i + 1}", start_page=start, end_page=end))
    return chapters
