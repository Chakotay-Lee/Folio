"""Analysis pipeline API endpoints."""
from __future__ import annotations
import io
import threading
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from backend.analysis.pipeline import AnalysisJob, AnalysisOptions, get_job, register_job, run_analysis
from backend.analysis.manifest import read_manifest

router = APIRouter(prefix="/api/books/{book_uuid}/analysis")


def _get_book_and_cfg(book_uuid: str, request: Request):
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select

    cfg = request.app.state.config
    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == book_uuid)).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book, cfg


def _get_pdf_path(book, cfg) -> Path:
    from backend.models.book import Book
    rel = book.relative_path
    file_path = Path(rel) if Path(rel).is_absolute() else cfg.storage.books_root / rel
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Book file not found on disk")
    return file_path


@router.get("/manifest")
def get_manifest(book_uuid: str, request: Request):
    """Return the analysis manifest.json for a book."""
    cfg = request.app.state.config
    manifest = read_manifest(cfg.analysis_dir / book_uuid)
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return manifest


@router.post("/trigger")
async def trigger_analysis(book_uuid: str, request: Request):
    """Start or re-start deep analysis for a book.

    Accepts an optional JSON body with AnalysisOptions fields:
      language, extra_prompt, analysis_model, extraction_model,
      page_start, page_end, mode
    """
    import json as _json
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select
    from datetime import datetime

    book, cfg = _get_book_and_cfg(book_uuid, request)

    # Parse options from request body (optional)
    try:
        body = await request.json()
    except Exception:
        body = {}
    opts = AnalysisOptions.from_dict(body if isinstance(body, dict) else {})

    # Allow re-trigger on done/failed; reject if already in-progress
    if book.analysis_status in ("queued", "analyzing"):
        return {"status": book.analysis_status, "message": "Analysis already in progress"}

    # Reset previous analysis data if re-analyzing
    analysis_dir = cfg.analysis_dir / book_uuid
    if analysis_dir.exists() and book.analysis_status in ("done", "failed"):
        import shutil
        shutil.rmtree(str(analysis_dir))

    # Persist options alongside analysis data
    analysis_dir.mkdir(parents=True, exist_ok=True)
    import dataclasses
    (analysis_dir / "analysis_options.json").write_text(
        _json.dumps(dataclasses.asdict(opts), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Update DB status
    with get_core_session() as session:
        b = session.exec(select(Book).where(Book.id == book_uuid)).first()
        if b:
            b.analysis_status = "queued"
            b.updated_at = datetime.utcnow()
            session.commit()

    file_path = _get_pdf_path(book, cfg)

    job = AnalysisJob(book_uuid=book_uuid, status="queued")
    register_job(job)

    t = threading.Thread(target=run_analysis, args=(book_uuid, file_path, cfg, opts), daemon=True)
    t.start()

    return {"status": "queued"}


@router.get("/progress")
def get_progress(book_uuid: str, request: Request):
    """Return current analysis progress."""
    book, cfg = _get_book_and_cfg(book_uuid, request)

    job = get_job(book_uuid)
    if job:
        return {
            "status": job.status,
            "stage": job.stage,
            "current_page": job.current_page,
            "total_pages": job.total_pages,
            "eta_seconds": job.eta_seconds(),
            "error": job.error or None,
        }

    # Fall back to manifest
    manifest = read_manifest(cfg.analysis_dir / book_uuid)
    if manifest:
        return {
            "status": manifest.get("status", book.analysis_status),
            "stage": manifest.get("status", "unknown"),
            "current_page": manifest.get("current_page", 0),
            "total_pages": manifest.get("total_pages", 0),
            "eta_seconds": None,
            "error": manifest.get("error") or None,
        }

    return {
        "status": book.analysis_status,
        "stage": book.analysis_status,
        "current_page": 0,
        "total_pages": 0,
        "eta_seconds": None,
        "error": None,
    }


@router.post("/cancel")
def cancel_analysis(book_uuid: str, request: Request):
    """Cancel an in-progress analysis."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select
    from datetime import datetime

    job = get_job(book_uuid)
    if not job or job.status not in ("queued", "analyzing"):
        raise HTTPException(status_code=400, detail="No active analysis job to cancel")

    job.cancelled = True
    job.status = "failed"

    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == book_uuid)).first()
        if book:
            book.analysis_status = "failed"
            book.updated_at = datetime.utcnow()
            session.commit()

    return {"status": "cancelled"}


@router.get("/audio/{filename}")
def get_audio(book_uuid: str, filename: str, request: Request):
    """Stream a generated audio file with Range support."""
    cfg = request.app.state.config
    audio_path = cfg.analysis_dir / book_uuid / "audio" / filename

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    file_size = audio_path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        start, end = _parse_range(range_header, file_size)
        length = end - start + 1
        with open(audio_path, "rb") as f:
            f.seek(start)
            data = f.read(length)
        return Response(
            content=data,
            status_code=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Type": "audio/mpeg",
            },
        )

    return StreamingResponse(
        open(audio_path, "rb"),
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
    )


@router.get("/export")
def export_html(book_uuid: str, request: Request):
    """Stream a ZIP archive of view.html + images/ directory."""
    book, cfg = _get_book_and_cfg(book_uuid, request)
    analysis_dir = cfg.analysis_dir / book_uuid
    view_html = analysis_dir / "view.html"

    if not view_html.exists():
        raise HTTPException(
            status_code=422,
            detail="view.html not found — re-run analysis to regenerate",
        )

    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(str(view_html), "view.html")
            images_dir = analysis_dir / "images"
            if images_dir.exists():
                for img_file in sorted(images_dir.iterdir()):
                    if img_file.suffix.lower() == ".png":
                        zf.write(str(img_file), f"images/{img_file.name}")
            chapters_dir = analysis_dir / "chapters"
            if chapters_dir.exists():
                for ch_file in sorted(chapters_dir.iterdir()):
                    if ch_file.suffix.lower() == ".html":
                        zf.write(str(ch_file), f"chapters/{ch_file.name}")
        buf.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")

    from urllib.parse import quote
    raw_title = book.title or book_uuid
    ascii_title = "".join(c if (c.isascii() and c.isalnum()) or c in "._- " else "_" for c in raw_title)
    ascii_filename = f"{ascii_title[:60] or 'export'}_export.zip"
    utf8_filename = f"{raw_title[:60]}_export.zip"
    disposition = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{quote(utf8_filename)}"

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )


@router.post("/rebuild-html")
def rebuild_html(book_uuid: str, request: Request):
    """Re-generate view.html and chapters/*.html from existing text/image files.

    Does NOT re-run OCR or LLM calls.  Safe to call after html_builder changes.
    Requires analysis status 'done'.
    """
    from backend.analysis.chapter_detector import Chapter
    from backend.analysis.image_extractor import ImageRecord
    from backend.analysis.html_builder import build_view_html, build_chapter_site

    book, cfg = _get_book_and_cfg(book_uuid, request)
    if book.analysis_status != "done":
        raise HTTPException(status_code=400, detail="Analysis must be complete before rebuilding HTML")

    analysis_dir = cfg.analysis_dir / book_uuid
    manifest = read_manifest(analysis_dir)
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")

    # Reconstruct Chapter and ImageRecord objects from manifest
    chapters = [
        Chapter(
            index=c["index"],
            title=c["title"],
            start_page=c["start_page"],
            end_page=c["end_page"],
        )
        for c in manifest.get("chapters", [])
    ]
    images = [
        ImageRecord(
            filename=i["filename"],
            page=i["page"],
            bbox=i.get("bbox", []),
            description=i.get("description", ""),
        )
        for i in manifest.get("images", [])
    ]

    text_dir = analysis_dir / "text"
    book_title = book.title or book_uuid

    # Rebuild single-page view.html
    view_html = build_view_html(book_title, chapters, images, text_dir)
    (analysis_dir / "view.html").write_text(view_html, encoding="utf-8")

    # Rebuild per-chapter site
    chapters_dir = analysis_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)
    ch_files = build_chapter_site(book_title, chapters, images, text_dir)
    for fname, content in ch_files.items():
        (chapters_dir / fname).write_text(content, encoding="utf-8")

    return {"status": "ok", "chapters": len(chapters), "images": len(images), "files": len(ch_files) + 1}


@router.get("/images/{filename}")
def get_analysis_image(book_uuid: str, filename: str, request: Request):
    """Serve an extracted figure image."""
    cfg = request.app.state.config
    img_path = cfg.analysis_dir / book_uuid / "images" / filename

    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return StreamingResponse(
        open(img_path, "rb"),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/chapters/{filename}")
def get_chapter_html(book_uuid: str, filename: str, request: Request):
    """Serve a per-chapter HTML file (index.html or ch_NN.html)."""
    from fastapi.responses import HTMLResponse
    cfg = request.app.state.config
    ch_path = cfg.analysis_dir / book_uuid / "chapters" / filename

    if not ch_path.exists() or ch_path.suffix.lower() != ".html":
        raise HTTPException(status_code=404, detail="Chapter file not found")

    return HTMLResponse(
        content=ch_path.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-cache"},
    )


def _parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    """Parse 'bytes=start-end' Range header."""
    try:
        unit, ranges = range_header.split("=")
        start_str, end_str = ranges.split("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        end = min(end, file_size - 1)
        return start, end
    except Exception:
        return 0, file_size - 1
