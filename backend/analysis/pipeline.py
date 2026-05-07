"""Background analysis pipeline orchestrator."""
from __future__ import annotations
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Job registry (in-memory) ──────────────────────────────────────────────────

@dataclass
class AnalysisJob:
    book_uuid: str
    status: str = "queued"          # queued | analyzing | done | failed
    current_page: int = 0
    total_pages: int = 0
    started_at: float = field(default_factory=time.time)
    stage: str = "queued"
    error: str = ""
    cancelled: bool = False
    _page_times: list[float] = field(default_factory=list, repr=False)

    def record_page(self) -> None:
        self._page_times.append(time.time())

    def eta_seconds(self) -> float | None:
        if len(self._page_times) < 3 or self.total_pages == 0:
            return None
        elapsed = self._page_times[-1] - self._page_times[0]
        avg = elapsed / len(self._page_times)
        remaining = self.total_pages - self.current_page
        return round(avg * remaining, 1)


_jobs: dict[str, AnalysisJob] = {}
_lock = threading.Lock()


def get_job(book_uuid: str) -> AnalysisJob | None:
    with _lock:
        return _jobs.get(book_uuid)


def register_job(job: AnalysisJob) -> None:
    with _lock:
        _jobs[job.book_uuid] = job


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_analysis(book_uuid: str, pdf_path: Path, cfg) -> None:
    """Main pipeline: runs in a background thread."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.analysis.chapter_detector import detect_chapters
    from backend.analysis.image_extractor import (
        extract_native_images, extract_scanned_images, describe_image, ImageRecord
    )
    from backend.analysis.summarizer import summarize_chapter
    from backend.analysis.html_builder import build_view_html
    from backend.analysis.manifest import init_manifest, update_manifest_page, finalize_manifest
    from backend.llm.factory import get_provider
    from sqlmodel import select

    job = get_job(book_uuid)
    if job is None:
        return

    analysis_dir = cfg.analysis_dir / book_uuid
    text_dir = analysis_dir / "text"
    images_dir = analysis_dir / "images"
    text_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    def set_status(status: str) -> None:
        job.status = status
        job.stage = status
        _update_book_status(book_uuid, status)

    try:
        import fitz
    except ImportError:
        log.error("PyMuPDF not installed — cannot run analysis")
        job.status = "failed"
        job.error = "PyMuPDF not installed"
        set_status("failed")
        return

    try:
        set_status("analyzing")
        job.stage = "chapter_detection"

        chapters = detect_chapters(pdf_path)
        doc = fitz.open(str(pdf_path))
        total_pages = doc.page_count
        job.total_pages = total_pages

        init_manifest(analysis_dir, book_uuid, total_pages)

        # Determine LLM providers
        analysis_model_cfg = cfg.llms.analysis_model or cfg.llms.extraction_model
        analysis_provider = get_provider(analysis_model_cfg)
        extraction_provider = get_provider(cfg.llms.extraction_model)

        img_counter = [0]
        all_images: list[ImageRecord] = []
        ch_texts: dict[int, str] = {}  # chapter index → text

        OCR_MIN = getattr(cfg.ocr, "min_chars_threshold", 50)

        # ── Per-page loop ──────────────────────────────────────────────────
        for page_num in range(total_pages):
            if job.cancelled:
                set_status("failed")
                doc.close()
                return

            job.current_page = page_num + 1
            job.stage = f"page_{page_num + 1}"
            page = doc[page_num]

            # Determine if page is native or scanned
            raw_text = page.get_text()
            is_scanned = len(raw_text.strip()) < OCR_MIN

            if is_scanned:
                # Render page as image for VLM
                mat = fitz.Matrix(2.0, 2.0)  # 2× scale for quality
                pix = page.get_pixmap(matrix=mat)
                from PIL import Image as PILImage
                import io
                img_bytes = pix.tobytes("png")
                page_img = PILImage.open(io.BytesIO(img_bytes))
                page_w, page_h = page_img.size

                # OCR text
                try:
                    from backend.analysis.image_extractor import _pil_to_b64, _call_vlm
                    b64 = _pil_to_b64(page_img)
                    ocr_text = _call_vlm(analysis_provider, "Extract all text from this page verbatim.", b64)
                except Exception as e:
                    log.warning("OCR failed page %d: %s", page_num, e)
                    ocr_text = ""

                # Figure detection
                page_images = extract_scanned_images(
                    page_img, page_num, images_dir, img_counter,
                    analysis_provider, page_w, page_h
                )
            else:
                ocr_text = raw_text
                page_images = extract_native_images(page, images_dir, img_counter)

            # Assign page text to chapter
            ch_idx = _page_to_chapter(page_num, chapters)
            if ch_idx is not None:
                ch_texts[ch_idx] = ch_texts.get(ch_idx, "") + (ocr_text or "") + "\n"

            # Describe extracted images
            for img_rec in page_images:
                img_path = images_dir / img_rec.filename
                describe_image(img_path, analysis_provider, img_rec)
                img_rec.model_used = analysis_model_cfg.model_name
                all_images.append(img_rec)

            job.record_page()
            update_manifest_page(analysis_dir, page_num + 1, {})

        doc.close()

        # ── Write chapter text files ───────────────────────────────────────
        job.stage = "writing_text"
        for ch in chapters:
            ch_file = text_dir / f"ch_{ch.index:02d}.txt"
            ch_file.write_text(ch_texts.get(ch.index, ""), encoding="utf-8")

        # ── Chapter summaries ─────────────────────────────────────────────
        job.stage = "summarizing"
        for ch in chapters:
            if job.cancelled:
                break
            ch_text = ch_texts.get(ch.index, "")
            summary = summarize_chapter(ch_text, extraction_provider, ch.title)
            summary_file = text_dir / f"ch_{ch.index:02d}_summary.txt"
            summary_file.write_text(summary, encoding="utf-8")

        # ── Image JSON sidecars ───────────────────────────────────────────
        import json
        for img in all_images:
            sidecar = images_dir / img.filename.replace(".png", ".json")
            sidecar.write_text(json.dumps({
                "page": img.page,
                "bbox": img.bbox,
                "description": img.description,
                "model_used": img.model_used,
                "tokens_used": img.tokens_used,
            }, ensure_ascii=False), encoding="utf-8")

        # ── HTML view ─────────────────────────────────────────────────────
        job.stage = "building_html"
        book_title = _get_book_title(book_uuid)
        html_content = build_view_html(book_title, chapters, all_images, text_dir)
        (analysis_dir / "view.html").write_text(html_content, encoding="utf-8")

        # ── Final manifest ────────────────────────────────────────────────
        finalize_manifest(
            analysis_dir,
            status="done",
            chapters=[{"index": c.index, "title": c.title,
                       "start_page": c.start_page, "end_page": c.end_page} for c in chapters],
            images=[{"filename": i.filename, "page": i.page, "bbox": i.bbox} for i in all_images],
        )

        set_status("done")
        log.info("Analysis complete for %s (%d pages, %d images)", book_uuid, total_pages, len(all_images))

    except Exception as e:
        log.exception("Analysis failed for %s: %s", book_uuid, e)
        job.error = str(e)
        try:
            from backend.analysis.manifest import finalize_manifest
            finalize_manifest(analysis_dir, status="failed", chapters=[], images=[], error=str(e))
        except Exception:
            pass
        set_status("failed")


def _update_book_status(book_uuid: str, status: str) -> None:
    try:
        from backend.db.core import get_core_session
        from backend.models.book import Book
        from sqlmodel import select
        from datetime import datetime
        with get_core_session() as session:
            book = session.exec(select(Book).where(Book.id == book_uuid)).first()
            if book:
                book.analysis_status = status
                book.updated_at = datetime.utcnow()
                session.commit()
    except Exception as e:
        log.warning("Failed to update book status for %s: %s", book_uuid, e)


def _page_to_chapter(page_num: int, chapters) -> int | None:
    for ch in chapters:
        if ch.start_page <= page_num < ch.end_page:
            return ch.index
    return None


def _get_book_title(book_uuid: str) -> str:
    try:
        from backend.db.core import get_core_session
        from backend.models.book import Book
        from sqlmodel import select
        with get_core_session() as session:
            book = session.exec(select(Book).where(Book.id == book_uuid)).first()
            return book.title if book else book_uuid
    except Exception:
        return book_uuid


def recover_stale_jobs(cfg) -> None:
    """On startup: mark any books stuck in 'analyzing' as 'failed'."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.analysis.manifest import read_manifest
    from sqlmodel import select
    from datetime import datetime

    try:
        with get_core_session() as session:
            stale = session.exec(
                select(Book).where(Book.analysis_status == "analyzing")
            ).all()
            for book in stale:
                manifest = read_manifest(cfg.analysis_dir / book.id)
                # If manifest says done it somehow wasn't written; if analyzing mark failed
                if manifest.get("status") != "done":
                    book.analysis_status = "failed"
                    book.updated_at = datetime.utcnow()
                    log.warning("Recovered stale analysis job for %s", book.id)
            session.commit()
    except Exception as e:
        log.warning("Startup recovery failed: %s", e)
