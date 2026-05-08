"""TTS audio generation — OpenAI API, local binary, AIVIS, or Gemini."""
from __future__ import annotations
import io
import logging
import re
import subprocess
import wave
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
        elif tts_cfg.provider == "aivis":
            part = _aivis_tts(chunk, tts_cfg)
        elif tts_cfg.provider == "gemini":
            part = _gemini_tts(chunk, tts_cfg)
        else:
            raise ValueError(f"Unknown TTS provider: {tts_cfg.provider}")
        audio_parts.append(part)

    if tts_cfg.provider in ("aivis", "gemini"):
        # WAV files must be properly merged, not naively concatenated
        output_path.write_bytes(_concat_wav(audio_parts))
    else:
        # Raw MP3 bytes can be concatenated directly
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


def _aivis_tts(text: str, tts_cfg) -> bytes:
    """AIVIS TTS (VOICEVOX-compatible): audio_query → synthesis → WAV."""
    import httpx

    base_url = (tts_cfg.base_url or "http://localhost:10101").rstrip("/")
    speaker = tts_cfg.speaker_id

    query_resp = httpx.post(
        f"{base_url}/audio_query",
        params={"text": text, "speaker": speaker},
        timeout=60,
    )
    query_resp.raise_for_status()

    synth_resp = httpx.post(
        f"{base_url}/synthesis",
        params={"speaker": speaker},
        content=query_resp.content,
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    synth_resp.raise_for_status()
    return synth_resp.content


def _gemini_tts(text: str, tts_cfg) -> bytes:
    """Gemini TTS via Google Generative Language API — wraps PCM response in WAV."""
    import base64
    import httpx

    api_key = tts_cfg.api_key
    if not api_key:
        raise ValueError("tts.api_key must be set for Gemini TTS provider")

    model = tts_cfg.model or "gemini-2.5-flash-preview-tts"
    voice = tts_cfg.voice or "Aoede"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {"prebuilt_voice_config": {"voice_name": voice}},
            },
        },
    }
    resp = httpx.post(url, json=payload, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    inline = data["candidates"][0]["content"]["parts"][0]["inlineData"]
    pcm_bytes = base64.b64decode(inline["data"])

    # Gemini returns raw PCM (audio/pcm;rate=24000) — wrap in WAV
    mime = inline.get("mimeType", "audio/pcm;rate=24000")
    rate = 24000
    if "rate=" in mime:
        try:
            rate = int(mime.split("rate=")[1].split(";")[0])
        except (IndexError, ValueError):
            pass

    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit PCM
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)
    return out.getvalue()


def _concat_wav(wav_parts: list[bytes]) -> bytes:
    """Merge multiple WAV byte strings into a single WAV."""
    if not wav_parts:
        return b""
    if len(wav_parts) == 1:
        return wav_parts[0]

    frames_list: list[bytes] = []
    params = None

    for part in wav_parts:
        with wave.open(io.BytesIO(part), "rb") as wf:
            if params is None:
                params = wf.getparams()
            frames_list.append(wf.readframes(wf.getnframes()))

    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setparams(params)  # type: ignore[arg-type]
        for frames in frames_list:
            wf.writeframes(frames)
    return out.getvalue()
