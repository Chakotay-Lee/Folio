"""Build self-contained view.html from analysis output."""
from __future__ import annotations
import html
from pathlib import Path

from backend.analysis.chapter_detector import Chapter
from backend.analysis.image_extractor import ImageRecord


def build_view_html(
    book_title: str,
    chapters: list[Chapter],
    images: list[ImageRecord],
    text_dir: Path,
) -> str:
    """Return HTML string with one <section> per chapter, figures interleaved by page."""

    # Index images by page for quick lookup
    images_by_page: dict[int, list[ImageRecord]] = {}
    for img in images:
        images_by_page.setdefault(img.page, []).append(img)

    sections = []
    for ch in chapters:
        ch_file = text_dir / f"ch_{ch.index:02d}.txt"
        ch_text = ch_file.read_text(encoding="utf-8") if ch_file.exists() else ""

        section_parts = [f'<section id="ch-{ch.index}">']
        section_parts.append(f"<h2>{html.escape(ch.title)}</h2>")

        # Collect page numbers in chapter order
        for page_num in range(ch.start_page, ch.end_page):
            # Insert figures that belong to this page
            for img in images_by_page.get(page_num, []):
                img_path = f"images/{img.filename}"
                desc = html.escape(img.description or img.filename)
                section_parts.append(
                    f'<figure>'
                    f'<img src="{img_path}" alt="{desc}" loading="lazy">'
                    f'<figcaption>{desc}</figcaption>'
                    f'</figure>'
                )

        # Append chapter text as paragraphs (after figures for simplicity)
        for para in ch_text.split("\n\n"):
            para = para.strip()
            if para:
                section_parts.append(f"<p>{html.escape(para)}</p>")

        section_parts.append("</section>")
        sections.append("\n".join(section_parts))

    toc_items = "".join(
        f'<li><a href="#ch-{ch.index}">{html.escape(ch.title)}</a></li>'
        for ch in chapters
    )

    body = "\n\n".join(sections)
    title_esc = html.escape(book_title)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.7; color: #222; }}
  h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
  h2 {{ font-size: 1.4rem; margin-top: 3rem; border-bottom: 1px solid #ccc; padding-bottom: 0.3rem; }}
  nav {{ background: #f8f8f8; padding: 1rem; border-radius: 4px; margin-bottom: 2rem; }}
  nav ol {{ margin: 0; padding-left: 1.5rem; }}
  figure {{ margin: 1.5rem 0; text-align: center; }}
  figure img {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px; }}
  figcaption {{ font-size: 0.9rem; color: #555; margin-top: 0.4rem; }}
  p {{ margin: 0.8rem 0; }}
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
