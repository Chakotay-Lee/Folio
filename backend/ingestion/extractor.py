import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {".pdf", ".epub", ".txt", ".md"}
OCR_CHAR_THRESHOLD = 50


def extract_text(file_path: str | Path, max_pages: int = 20, use_ocr: bool = True) -> str:
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        logger.warning("Unsupported file type: %s — skipping", ext)
        return ""
    if ext == ".pdf":
        return _extract_pdf(path, max_pages, use_ocr=use_ocr)
    if ext == ".epub":
        return _extract_epub(path, max_pages)
    return _extract_text_file(path)


def _extract_pdf(path: Path, max_pages: int, use_ocr: bool = True) -> str:
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    pages_to_read = min(max_pages, len(doc))
    parts: list[str] = []
    ocr_pages: list[int] = []

    for i in range(pages_to_read):
        text = doc[i].get_text()
        if len(text.strip()) < OCR_CHAR_THRESHOLD:
            ocr_pages.append(i)
        else:
            parts.append(text)

    if use_ocr and ocr_pages:
        ocr_text = _ocr_pdf_pages(doc, ocr_pages)
        parts.extend(ocr_text)

    doc.close()
    return "\n".join(parts)


def _ocr_pdf_pages(doc, page_indices: list[int]) -> list[str]:
    from backend.ingestion.ocr import run_ocr

    results = []
    for i in page_indices:
        pix = doc[i].get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        text = run_ocr(img_bytes)
        if text:
            results.append(text)
    return results


def _extract_epub(path: Path, max_items: int) -> str:
    import ebooklib
    from ebooklib import epub
    import re

    book = epub.read_epub(str(path), {"ignore_ncx": True})
    items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))[:max_items]
    parts = []
    for item in items:
        html = item.get_content().decode("utf-8", errors="ignore")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _extract_text_file(path: Path, max_chars: int = 20_000) -> str:
    content = path.read_text(encoding="utf-8", errors="ignore")
    return content[:max_chars]
