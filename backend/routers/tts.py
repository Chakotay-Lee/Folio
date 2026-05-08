"""TTS generation endpoints."""
from __future__ import annotations
import re as _re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel


def _clean_for_tts(text: str) -> str:
    """Strip markdown syntax that sounds terrible when read aloud.

    Removes [[PAGE:N]] markers, markdown table pipes/separators, and heading
    markers (##), leaving only readable natural-language content.
    """
    out: list[str] = []
    for line in text.splitlines():
        # Page markers
        line = _re.sub(r'\[\[PAGE:\d+\]\]', '', line)
        # Skip separator rows (| --- | --- |)
        if _re.match(r'^\s*\|[\s:\-|]+\|\s*$', line):
            continue
        # Table data rows: strip leading/trailing pipes and join cells with spaces
        if _re.match(r'^\s*\|', line) and line.rstrip().endswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|') if c.strip()]
            if cells:
                out.append('  '.join(cells))
            continue
        # Heading markers (##, ###, …)
        line = _re.sub(r'^#{1,6}\s+', '', line)
        out.append(line)
    return '\n'.join(out)

router = APIRouter(prefix="/api/books/{book_uuid}/analysis")

# Utility router — not book-scoped
util_router = APIRouter(prefix="/api/tts")


@util_router.get("/aivis-speakers")
async def aivis_speakers(base_url: str = Query(default="http://localhost:10101")):
    """Proxy GET /speakers to the AIVIS server (avoids browser CORS restrictions)."""
    import httpx
    url = base_url.rstrip("/") + "/speakers"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"AIVIS returned {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach AIVIS server: {e}")


class TTSRequest(BaseModel):
    chapter: int
    mode: str       # "summary" | "full"
    force: bool = False


@router.post("/tts")
async def generate_tts(book_uuid: str, body: TTSRequest, request: Request):
    """Generate TTS audio for a chapter (cached)."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.analysis.tts import generate_audio
    from sqlmodel import select

    cfg = request.app.state.config
    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == book_uuid)).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.analysis_status != "done":
        raise HTTPException(status_code=400, detail="Analysis must be complete before generating audio")

    if body.mode not in ("summary", "full"):
        raise HTTPException(status_code=422, detail="mode must be 'summary' or 'full'")

    tts_cfg = cfg.tts
    if tts_cfg.provider == "openai" and not tts_cfg.api_key:
        raise HTTPException(status_code=422, detail="TTS not configured: tts.api_key is missing")
    if tts_cfg.provider == "local" and not tts_cfg.binary_path:
        raise HTTPException(status_code=422, detail="TTS not configured: tts.binary_path is missing")
    if tts_cfg.provider == "gemini" and not tts_cfg.api_key:
        raise HTTPException(status_code=422, detail="TTS not configured: tts.api_key is missing for Gemini")
    if tts_cfg.provider not in ("openai", "local", "aivis", "gemini"):
        raise HTTPException(status_code=422, detail=f"Unknown TTS provider: {tts_cfg.provider!r}")

    text_dir = cfg.analysis_dir / book_uuid / "text"
    audio_dir = cfg.analysis_dir / book_uuid / "audio"

    ext = "wav" if tts_cfg.provider in ("aivis", "gemini") else "mp3"
    ch_idx = body.chapter
    if body.mode == "summary":
        source_file = text_dir / f"ch_{ch_idx:02d}_summary.txt"
        audio_file = audio_dir / f"ch_{ch_idx:02d}_summary.{ext}"
    else:
        source_file = text_dir / f"ch_{ch_idx:02d}.txt"
        audio_file = audio_dir / f"ch_{ch_idx:02d}_full.{ext}"

    if not source_file.exists():
        raise HTTPException(status_code=404, detail=f"Chapter {ch_idx} text not found")

    # If force-regenerate, delete any existing audio for this chapter+mode (all extensions)
    mode_suffix = "summary" if body.mode == "summary" else "full"
    if body.force and audio_dir.exists():
        for old in audio_dir.glob(f"ch_{ch_idx:02d}_{mode_suffix}.*"):
            old.unlink(missing_ok=True)

    # Return cached audio if available
    if not body.force and audio_file.exists():
        audio_url = f"/api/books/{book_uuid}/analysis/audio/{audio_file.name}"
        return {"audio_url": audio_url, "cached": True}

    text = _clean_for_tts(source_file.read_text(encoding="utf-8"))
    if not text.strip():
        raise HTTPException(status_code=422, detail="Chapter text is empty")

    try:
        generate_audio(text, tts_cfg, audio_file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")

    audio_url = f"/api/books/{book_uuid}/analysis/audio/{audio_file.name}"
    return {"audio_url": audio_url, "cached": False}


@router.get("/tts-cache")
async def tts_cache_status(book_uuid: str, request: Request):
    """Return a map of {chapterIndex-mode: audioUrl} for all cached TTS files."""
    import re as _re
    cfg = request.app.state.config
    audio_dir = cfg.analysis_dir / book_uuid / "audio"
    if not audio_dir.exists():
        return {}

    result: dict[str, str] = {}
    for f in audio_dir.iterdir():
        m = _re.match(r'^ch_0*(\d+)_(summary|full)\.\w+$', f.name)
        if m:
            key = f"{int(m.group(1))}-{m.group(2)}"
            result[key] = f"/api/books/{book_uuid}/analysis/audio/{f.name}"
    return result
