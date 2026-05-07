"""TTS generation endpoints."""
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/books/{book_uuid}/analysis")


class TTSRequest(BaseModel):
    chapter: int
    mode: str  # "summary" | "full"


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
    if tts_cfg.provider not in ("openai", "local"):
        raise HTTPException(status_code=422, detail=f"Unknown TTS provider: {tts_cfg.provider!r}")

    text_dir = cfg.analysis_dir / book_uuid / "text"
    audio_dir = cfg.analysis_dir / book_uuid / "audio"

    ch_idx = body.chapter
    if body.mode == "summary":
        source_file = text_dir / f"ch_{ch_idx:02d}_summary.txt"
        audio_file = audio_dir / f"ch_{ch_idx:02d}_summary.mp3"
    else:
        source_file = text_dir / f"ch_{ch_idx:02d}.txt"
        audio_file = audio_dir / f"ch_{ch_idx:02d}_full.mp3"

    if not source_file.exists():
        raise HTTPException(status_code=404, detail=f"Chapter {ch_idx} text not found")

    # Return cached audio if available
    if audio_file.exists():
        audio_url = f"/api/books/{book_uuid}/analysis/audio/{audio_file.name}"
        return {"audio_url": audio_url, "cached": True}

    text = source_file.read_text(encoding="utf-8")
    if not text.strip():
        raise HTTPException(status_code=422, detail="Chapter text is empty")

    try:
        generate_audio(text, tts_cfg, audio_file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")

    audio_url = f"/api/books/{book_uuid}/analysis/audio/{audio_file.name}"
    return {"audio_url": audio_url, "cached": False}
