"""Chapter summary generation via LLM."""
from __future__ import annotations
import logging

log = logging.getLogger(__name__)

MAX_SUMMARY_WORDS = 300
# Rough char limit before truncating (4 chars/token × 80K-token buffer)
CONTEXT_CHAR_LIMIT = 320_000


def summarize_chapter(
    text: str,
    provider,
    chapter_title: str = "",
    language: str = "",
    extra_prompt: str = "",
) -> str:
    """Return a ≤300-word summary of chapter text using the given LLM provider."""
    import re as _re
    if not text.strip():
        return ""

    # Strip page markers before summarizing
    clean = _re.sub(r'\[\[PAGE:\d+\]\]\n?', '', text)

    body, truncated = _prepare_text(clean)
    truncation_note = "\n\n[Note: chapter was too long; only the first and last 20% was summarized.]" if truncated else ""

    lang_note  = f" Write the summary in {language}." if language else ""
    extra_note = f"\n\nAdditional instructions: {extra_prompt}" if extra_prompt else ""

    prompt = (
        f"Summarize the following {'chapter' if not chapter_title else repr(chapter_title)} "
        f"in {MAX_SUMMARY_WORDS} words or fewer.{lang_note} Be concise and focus on key ideas.\n\n"
        f"{body}"
        + extra_note
    )

    try:
        result = provider.extract_metadata.__func__  # check if it's a proper provider
    except AttributeError:
        pass

    try:
        # Use raw completion if the provider exposes it; otherwise fall back to extract_metadata
        if hasattr(provider, "complete"):
            summary = provider.complete(prompt)
        else:
            # Wrap in extract_metadata-style call is not ideal; use direct HTTP instead
            summary = _call_provider_raw(provider, prompt)
    except Exception as e:
        log.warning("Summarizer LLM call failed: %s", e)
        return ""

    return (summary.strip() + truncation_note)[:2000]


def _prepare_text(text: str) -> tuple[str, bool]:
    """Return (body, truncated). Truncates to first+last 20% if over limit."""
    if len(text) <= CONTEXT_CHAR_LIMIT:
        return text, False

    chunk = int(len(text) * 0.20)
    first = text[:chunk]
    last = text[-chunk:]
    return first + "\n\n[...]\n\n" + last, True


def _call_provider_raw(provider, prompt: str) -> str:
    """Call OpenAI-compatible provider with a plain text prompt."""
    import httpx

    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": provider.model_name,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": provider.max_tokens,
        "temperature": provider.temperature,
    }
    if hasattr(provider, "extra_body") and provider.extra_body:
        payload.update(provider.extra_body)

    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"

    resp = httpx.post(url, json=payload, headers=headers, timeout=provider.timeout_seconds)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""
