"""TTS audio generation — OpenAI API or local binary."""
from __future__ import annotations
import io
import logging
import re
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def generate_audio(text: str, tts_cfg, output_path: Path) -> None:
    """Generate audio from text and save to output_path (MP3)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = _split_text(text, tts_cfg.chunk_size)
    audio_parts: list[bytes] = []

    for chunk in chunks:
        if tts_cfg.provider == "openai":
            part = _openai_tts(chunk, tts_cfg)
        elif tts_cfg.provider == "local":
            part = _local_tts(chunk, tts_cfg)
        else:
            raise ValueError(f"Unknown TTS provider: {tts_cfg.provider}")
        audio_parts.append(part)

    # Concatenate raw MP3 bytes (valid for simple concatenation of same-format segments)
    output_path.write_bytes(b"".join(audio_parts))


def _split_text(text: str, chunk_size: int) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    # Split on sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?。！？])\s+', text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= chunk_size:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            # If a single sentence exceeds chunk_size, force-split it
            if len(sentence) > chunk_size:
                for i in range(0, len(sentence), chunk_size):
                    chunks.append(sentence[i:i + chunk_size])
                current = ""
            else:
                current = sentence

    if current:
        chunks.append(current)

    return chunks or [text]


def _openai_tts(text: str, tts_cfg) -> bytes:
    import httpx

    base_url = "https://api.openai.com/v1"
    url = f"{base_url}/audio/speech"
    payload = {
        "model": tts_cfg.model,
        "input": text,
        "voice": tts_cfg.voice,
        "response_format": "mp3",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {tts_cfg.api_key}",
    }
    resp = httpx.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.content


def _local_tts(text: str, tts_cfg) -> bytes:
    """Call a local TTS binary (Kokoro/Piper) with text on stdin."""
    if not tts_cfg.binary_path:
        raise ValueError("tts.binary_path must be set for local TTS provider")

    result = subprocess.run(
        [tts_cfg.binary_path],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Local TTS failed: {result.stderr.decode()[:200]}")
    return result.stdout
