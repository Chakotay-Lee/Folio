"""Build self-contained view.html from analysis output."""
from __future__ import annotations
import html
import json as _json
import re
from pathlib import Path

from backend.analysis.chapter_detector import Chapter
from backend.analysis.image_extractor import ImageRecord

# Any ``` ... ``` code block (capturing lang tag and body separately)
_CODE_BLOCK_RE = re.compile(r'```(\w*)\s*\n(.*?)\n```', re.DOTALL)
_BODY_RE = re.compile(r'<body>(.*?)</body>', re.DOTALL | re.IGNORECASE)


def _plain_lines_to_html(text: str) -> list[str]:
    """Wrap non-empty lines in <p> with HTML-escaped content."""
    parts = []
    for para in re.split(r'\n{2,}', text):
        para = para.strip()
        if not para:
            continue
        lines = [l.strip() for l in para.splitlines() if l.strip()]
        if lines:
            parts.append(f"<p>{html.escape(' '.join(lines))}</p>")
    return parts


def _json_block_to_html(json_text: str) -> list[str]:
    """Extract text_content (or text/content) fields from a JSON OCR block."""
    try:
        data = _json.loads(json_text)
    except _json.JSONDecodeError:
        # Try relaxing backslash escapes (LaTeX in text_content)
        fixed = re.sub(r'\\(?!["\\])', r'\\\\', json_text)
        try:
            data = _json.loads(fixed)
        except _json.JSONDecodeError:
            return _plain_lines_to_html(json_text)

    if not isinstance(data, list):
        return _plain_lines_to_html(str(data))

    parts = []
    for item in data:
        if not isinstance(item, dict):
            continue
        t = item.get("text_content") or item.get("text") or item.get("content", "")
        t = str(t).strip()
        if t:
            # Preserve LaTeX inline/display markers; escape HTML special chars
            # but don't escape $ signs (KaTeX will process them)
            parts.append(f"<p>{html.escape(t)}</p>")
    return parts


def _chapter_text_to_html(text: str) -> str:
    """Convert chapter text to an HTML fragment.

    VLMs produce a mix of output formats across pages:
      - ```html blocks  → extract <body> content, insert verbatim
      - ```json blocks  → extract text_content fields, wrap in <p>
      - ``` (plain)     → treat content as plain text paragraphs
      - plain text      → wrap in <p>, preserve $...$ LaTeX

    LaTeX formulas ($...$, $$...$$) are left intact for KaTeX auto-render.
    """
    parts: list[str] = []
    last_end = 0

    for m in _CODE_BLOCK_RE.finditer(text):
        lang = m.group(1).lower()
        block = m.group(2)

        # ── plain text before this block ──────────────────────────────────
        before = text[last_end:m.start()].strip()
        if before:
            parts.extend(_plain_lines_to_html(before))

        # ── dispatch by language tag ──────────────────────────────────────
        if lang == "html":
            body_m = _BODY_RE.search(block)
            inner = body_m.group(1).strip() if body_m else block.strip()
            if inner:
                parts.append(inner)
        elif lang == "json":
            parts.extend(_json_block_to_html(block))
        else:
            # plain ``` or unknown lang — try JSON, fall back to plain text
            json_parts = _json_block_to_html(block)
            if json_parts:
                parts.extend(json_parts)
            else:
                parts.extend(_plain_lines_to_html(block))

        last_end = m.end()

    # ── remaining text after last block ───────────────────────────────────
    remaining = text[last_end:].strip()
    if remaining:
        parts.extend(_plain_lines_to_html(remaining))

    return "\n".join(parts)


def build_view_html(
    book_title: str,
    chapters: list[Chapter],
    images: list[ImageRecord],
    text_dir: Path,
) -> str:
    """Return HTML string with one <section> per chapter, figures interleaved by page."""

    images_by_page: dict[int, list[ImageRecord]] = {}
    for img in images:
        images_by_page.setdefault(img.page, []).append(img)

    sections: list[str] = []
    for ch in chapters:
        ch_file = text_dir / f"ch_{ch.index:02d}.txt"
        ch_text = ch_file.read_text(encoding="utf-8") if ch_file.exists() else ""

        section_parts = [f'<section id="ch-{ch.index}">']
        section_parts.append(f"<h2>{html.escape(ch.title)}</h2>")

        for page_num in range(ch.start_page, ch.end_page):
            for img in images_by_page.get(page_num, []):
                img_path = f"images/{img.filename}"
                desc = html.escape(img.description or img.filename)
                section_parts.append(
                    f'<figure>'
                    f'<img src="{img_path}" alt="{desc}" loading="lazy">'
                    f'<figcaption>{desc}</figcaption>'
                    f'</figure>'
                )

        section_parts.append(_chapter_text_to_html(ch_text))
        section_parts.append("</section>")
        sections.append("\n".join(section_parts))

    toc_items = "".join(
        f'<li><a href="#ch-{ch.index}">{html.escape(ch.title)}</a></li>'
        for ch in chapters
    )

    body = "\n\n".join(sections)
    title_esc = html.escape(book_title)

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc}</title>
<!-- KaTeX for fast LaTeX rendering -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body, {{
    delimiters: [
      {{left: '$$', right: '$$', display: true}},
      {{left: '$',  right: '$',  display: false}}
    ],
    throwOnError: false
  }});"></script>
<style>
  body {{ font-family: 'Noto Serif SC', Georgia, serif; max-width: 860px; margin: 2rem auto; padding: 0 1.2rem; line-height: 1.8; color: #1a1a1a; }}
  h1 {{ font-size: 2rem; margin-bottom: 0.4rem; }}
  h2 {{ font-size: 1.35rem; margin-top: 3rem; border-bottom: 1px solid #d0d0d0; padding-bottom: 0.3rem; }}
  h3 {{ font-size: 1.1rem; margin-top: 1.8rem; }}
  nav {{ background: #f6f6f6; padding: 1rem 1.2rem; border-radius: 6px; margin-bottom: 2.5rem; }}
  nav ol {{ margin: 0; padding-left: 1.5rem; column-count: 2; }}
  nav li {{ margin: 0.15rem 0; font-size: 0.9rem; }}
  section {{ margin-bottom: 3rem; }}
  p {{ margin: 0.7rem 0; text-align: justify; }}
  ol, ul {{ margin: 0.5rem 0 0.5rem 1.5rem; }}
  figure {{ margin: 1.8rem 0; text-align: center; }}
  figure img {{ max-width: 100%; height: auto; border: 1px solid #e0e0e0; border-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }}
  figcaption {{ font-size: 0.88rem; color: #666; margin-top: 0.5rem; font-style: italic; }}
  .formula {{ margin: 1.2rem 0; text-align: center; overflow-x: auto; }}
  .formula img {{ display: none; }}  /* placeholder images from VLM output */
  .katex-display {{ margin: 0.8rem 0; }}
  pre {{ background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>{title_esc}</h1>
<nav>
  <ol>{toc_items}</ol>
</nav>

{body}
</body>
</html>"""
