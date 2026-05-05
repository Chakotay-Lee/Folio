import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TARGET_WIDTH = 300   # thumbnail width in pixels


def extract_cover(file_path: Path, uuid: str, assets_dir: Path) -> bool:
    """Extract cover thumbnail to assets/covers/{uuid}.jpg. Returns True on success."""
    covers_dir = assets_dir / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    out_path = covers_dir / f"{uuid}.jpg"

    if out_path.exists():
        return True

    ext = file_path.suffix.lower()
    try:
        if ext == ".pdf":
            return _pdf_cover(file_path, out_path)
        elif ext == ".epub":
            return _epub_cover(file_path, out_path)
    except Exception as e:
        logger.warning("Cover extraction failed for %s: %s", file_path.name, e)
    return False


def _pdf_cover(pdf_path: Path, out_path: Path) -> bool:
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    if len(doc) == 0:
        return False
    page = doc[0]
    # Scale so width = TARGET_WIDTH
    w = page.rect.width or 1
    zoom = TARGET_WIDTH / w
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    pix.save(str(out_path))
    doc.close()
    return out_path.exists()


def _epub_cover(epub_path: Path, out_path: Path) -> bool:
    import ebooklib
    from ebooklib import epub

    book = epub.read_epub(str(epub_path), {"ignore_ncx": True})

    # Prefer item whose name contains "cover"
    candidates = [
        item for item in book.get_items()
        if item.media_type in ("image/jpeg", "image/png", "image/gif", "image/webp")
    ]
    cover_item = next(
        (i for i in candidates if "cover" in i.get_name().lower()),
        candidates[0] if candidates else None,
    )
    if cover_item is None:
        return False

    raw = cover_item.get_content()
    # Convert to JPEG via PIL if it's not already
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = img.size
        new_w = TARGET_WIDTH
        new_h = int(h * new_w / w)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        img.save(str(out_path), "JPEG", quality=85)
    except ImportError:
        out_path.write_bytes(raw)

    return out_path.exists()
