"""Context assembly for Book Chat — summaries only; chapters fetched on demand via tools."""
from __future__ import annotations
import json
from pathlib import Path

# If a book has no summaries and its full text fits here, include it directly
SMALL_BOOK_CHAR_LIMIT = 40_000


def _load_chapters(analysis_dir: Path) -> list[dict]:
    """Return chapters list from manifest, or [] if unavailable."""
    manifest = analysis_dir / "manifest.json"
    if not manifest.exists():
        return []
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("chapters", [])
    except Exception:
        return []


def _page_to_chapter(page: int, chapters: list[dict]) -> int | None:
    for ch in chapters:
        if ch["start_page"] <= page < ch["end_page"]:
            return ch["index"]
    return None


def assemble_context(analysis_dir: Path) -> str:
    """
    Return chapter summaries as the baseline system context.
    Full chapter text is fetched on demand via the get_chapter_content tool.
    Falls back to full text for very short books with no summaries.
    """
    text_dir = analysis_dir / "text"
    if not text_dir.exists():
        return ""

    chapters = _load_chapters(analysis_dir)
    ch_meta = {ch["index"]: ch for ch in chapters}

    summary_files = sorted(text_dir.glob("ch_??_summary.txt"))
    if summary_files:
        parts = []
        for f in summary_files:
            try:
                idx = int(f.stem.split("_")[1])
            except (IndexError, ValueError):
                idx = None
            meta = ch_meta.get(idx) if idx is not None else None
            if meta:
                header = (
                    f"[Chapter {idx}: {meta['title']} "
                    f"(pages {meta['start_page'] + 1}–{meta['end_page']})]"
                )
            elif idx is not None:
                header = f"[Chapter {idx}]"
            else:
                header = "[Chapter]"
            parts.append(header + "\n" + f.read_text(encoding="utf-8"))
        return "[Chapter Summaries]\n\n" + "\n\n---\n\n".join(parts)

    # No summaries yet — fall back to full text if it's small enough
    text_files = sorted(text_dir.glob("ch_??.txt"))
    if not text_files:
        return ""
    parts = [f.read_text(encoding="utf-8") for f in text_files]
    full = "\n\n---\n\n".join(parts)
    if len(full) <= SMALL_BOOK_CHAR_LIMIT:
        return f"[Book Content]\n\n{full}"
    return f"[Book Content (truncated)]\n\n{full[:SMALL_BOOK_CHAR_LIMIT]}\n[...use get_chapter_content for more]"


def get_chapter_content(analysis_dir: Path, chapter_index: int, max_chars: int = 40_000) -> str:
    """Fetch the full text of a single chapter (called when LLM requests it)."""
    ch_file = analysis_dir / "text" / f"ch_{chapter_index:02d}.txt"
    if not ch_file.exists():
        return f"Chapter {chapter_index} not found."
    text = ch_file.read_text(encoding="utf-8")
    if len(text) > max_chars:
        return text[:max_chars] + "\n[...truncated]"
    return text


def build_image_list(analysis_dir: Path) -> str:
    """Return a compact text list of available figures, annotated with chapter, for the LLM context."""
    images_dir = analysis_dir / "images"
    if not images_dir.exists():
        return ""

    chapters = _load_chapters(analysis_dir)

    lines = []
    for json_file in sorted(images_dir.glob("img_???.json")):
        try:
            meta = json.loads(json_file.read_text(encoding="utf-8"))
            img_id = json_file.stem
            desc = meta.get("description", "")
            page = meta.get("page")
            ch_idx = _page_to_chapter(page, chapters) if page is not None else None
            ch_label = f"ch{ch_idx}" if ch_idx is not None else "?"
            page_label = page + 1 if page is not None else "?"
            lines.append(f"{img_id} | ch{ch_idx if ch_idx is not None else '?'} p{page_label} | {desc[:80]}")
        except Exception:
            continue

    if not lines:
        return ""
    return (
        "[Available Figures — write exactly [img_NNN] to display one]\n"
        + "\n".join(lines)
    )
