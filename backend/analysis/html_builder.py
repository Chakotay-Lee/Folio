"""Build self-contained view.html from analysis output."""
from __future__ import annotations
import html
import re
from pathlib import Path

from backend.analysis.chapter_detector import Chapter
from backend.analysis.image_extractor import ImageRecord

# Matches ```html\n<html><body>...</body></html>\n```
_HTML_BLOCK_RE = re.compile(r'```html\s*\n(.*?)\n```', re.DOTALL)
_BODY_RE = re.compile(r'<body>(.*?)</body>', re.DOTALL | re.IGNORECASE)


def _chapter_text_to_html(text: str) -> str:
    """Convert chapter text (mix of plain text + ```html blocks) to HTML fragment.

    VLMs tend to emit structured pages as ```html ... ``` code blocks.  Extract
    the <body> content from those blocks and insert it directly.  Remaining
    plain-text is wrapped in <p> tags.  LaTeX ($...$, $$...$$) is preserved as-is
    for MathJax to render on the client side.
    """
    parts: list[str] = []
    last_end = 0

    for m in _HTML_BLOCK_RE.finditer(text):
        # ── plain text before this block ──────────────────────────────────
        before = text[last_end:m.start()].strip()
        if before:
            for line in before.splitlines():
                line = line.strip()
                if line:
                    parts.append(f"<p>{html.escape(line)}</p>")

        # ── HTML block: extract <body> content ────────────────────────────
        block = m.group(1)
        body_m = _BODY_RE.search(block)
        inner = body_m.group(1).strip() if body_m else block.strip()
        if inner:
            parts.append(inner)

        last_end = m.end()

    # ── remaining text after last block ───────────────────────────────────
    remaining = text[last_end:].strip()
    if remaining:
        for line in remaining.splitlines():
            line = line.strip()
            if line:
                parts.append(f"<p>{html.escape(line)}</p>")

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
