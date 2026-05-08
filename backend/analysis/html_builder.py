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
# Page boundary markers inserted by pipeline: [[PAGE:N]]
_PAGE_MARKER_RE = re.compile(r'\[\[PAGE:(\d+)\]\]\n?')

# Markdown heading: # through ###### at start of line
_MD_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$')
# Numbered section heading: "1.2 Title", "1.2.3 Title" (short line, not mid-paragraph)
_NUM_HEADING_RE = re.compile(r'^(\d+(?:\.\d+)+)\s+(\S.{0,90})$')
# Chinese chapter/section heading: 第N章 Title  (requires title text after marker)
_ZH_HEADING_RE  = re.compile(r'^第\s*[〇一二三四五六七八九十百千\d]+\s*[章節节篇部]\s*\S')
# Standalone chapter number with no title: 第N章  (just the marker, nothing after)
_ZH_CH_NUM_RE   = re.compile(r'^第\s*[〇一二三四五六七八九十百千\d]+\s*[章節节篇部]\s*$')
# Markdown table row: starts and ends with pipe, or contains multiple pipes
_TABLE_ROW_RE = re.compile(r'^\|.+\|')
# Separator row: | --- | :---: |
_TABLE_SEP_RE = re.compile(r'^\|[\s\-:|]+\|')
# Inline markdown
_BOLD_RE    = re.compile(r'\*\*(.+?)\*\*')
_ITALIC_RE  = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')
_MATH_PROT2 = re.compile(r'\$\$[\s\S]*?\$\$|\$[^\n$]+?\$')
# List item markers
_UL_ITEM_RE = re.compile(r'^[\*\-]\s+(.+)$')
_OL_ITEM_RE = re.compile(r'^\d+[\.\)]\s+(.+)$')


def _md_inline(escaped: str) -> str:
    """Apply bold/italic to already-html-escaped text, protecting LaTeX spans."""
    protected: list[str] = []

    def _prot(m: re.Match) -> str:
        n = len(protected)
        protected.append(m.group(0))
        return f'\x02{n:04d}\x02'

    t = _MATH_PROT2.sub(_prot, escaped)
    t = _BOLD_RE.sub(r'<strong>\1</strong>', t)
    t = _ITALIC_RE.sub(r'<em>\1</em>', t)
    for n, v in enumerate(protected):
        t = t.replace(f'\x02{n:04d}\x02', v)
    return t


def _md_table_to_html(lines: list[str]) -> str | None:
    """Convert a list of markdown table lines to an HTML <table>.

    Returns None if the lines don't look like a valid markdown table.
    """
    if len(lines) < 2:
        return None
    # Find separator row
    sep_idx = next(
        (i for i, l in enumerate(lines) if _TABLE_SEP_RE.match(l.strip())),
        None,
    )
    if sep_idx is None:
        return None

    def _parse_row(line: str) -> list[str]:
        stripped = line.strip().strip('|')
        return [_md_inline(html.escape(cell.strip())) for cell in stripped.split('|')]

    header_lines = lines[:sep_idx]
    data_lines   = lines[sep_idx + 1:]

    buf = ['<table>']
    if header_lines:
        buf.append('<thead>')
        for row in header_lines:
            cells = _parse_row(row)
            buf.append('<tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr>')
        buf.append('</thead>')
    if data_lines:
        buf.append('<tbody>')
        for row in data_lines:
            if not row.strip():
                continue
            cells = _parse_row(row)
            buf.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
        buf.append('</tbody>')
    buf.append('</table>')
    return '\n'.join(buf)


def _line_is_heading(line: str) -> str | None:
    """Return the HTML tag name if line is a heading, else None."""
    m = _MD_HEADING_RE.match(line)
    if m:
        return f'h{min(len(m.group(1)) + 1, 4)}'
    if (_ZH_HEADING_RE.match(line) or _ZH_CH_NUM_RE.match(line)) and len(line) <= 80:
        return 'h2'
    if _NUM_HEADING_RE.match(line) and len(line) <= 100:
        return 'h3'
    return None


def _emit_line_heading(line: str, parts: list[str]) -> None:
    """Emit a single heading line as the appropriate <hN> element."""
    m = _MD_HEADING_RE.match(line)
    if m:
        level = min(len(m.group(1)) + 1, 4)
        full_text = m.group(2).strip()
        # Split "## ShortTitle LongBody..." into heading + body paragraph
        if len(full_text) > 35:
            sp = full_text.find(' ', 2)
            if 2 < sp < 35:
                body = full_text[sp:].strip()
                full_text = full_text[:sp]
                parts.append(f'<h{level}>{_md_inline(html.escape(full_text))}</h{level}>')
                parts.append(f'<p>{_md_inline(html.escape(body))}</p>')
                return
        parts.append(f'<h{level}>{_md_inline(html.escape(full_text))}</h{level}>')
        return
    if (_ZH_HEADING_RE.match(line) or _ZH_CH_NUM_RE.match(line)) and len(line) <= 80:
        parts.append(f'<h2>{_md_inline(html.escape(line))}</h2>')
        return
    if _NUM_HEADING_RE.match(line) and len(line) <= 100:
        parts.append(f'<h3>{_md_inline(html.escape(line))}</h3>')


def _lines_to_html_parts(clean_lines: list[str], parts: list[str]) -> None:
    """Process a list of cleaned lines into HTML parts, handling mixed heading/body."""
    para_acc: list[str] = []
    for line in clean_lines:
        if _line_is_heading(line):
            if para_acc:
                parts.append(f'<p>{_md_inline(html.escape(" ".join(para_acc)))}</p>')
                para_acc = []
            _emit_line_heading(line, parts)
        else:
            para_acc.append(line)
    if para_acc:
        parts.append(f'<p>{_md_inline(html.escape(" ".join(para_acc)))}</p>')


def _plain_lines_to_html(text: str) -> list[str]:
    """Convert plain text with optional markdown to HTML fragments.

    Handles: ## headings, * / - / 1. lists, **bold**, *italic*, pipe tables.
    LaTeX $...$ spans are protected from inline-markdown substitution.
    """
    parts: list[str] = []

    for para in re.split(r'\n{2,}', text):
        para = para.strip()
        if not para:
            continue

        lines = para.splitlines()

        # ── Markdown table block ──────────────────────────────────────────
        if any(_TABLE_ROW_RE.match(l.strip()) for l in lines):
            table_html = _md_table_to_html([l.strip() for l in lines])
            if table_html:
                parts.append(table_html)
                continue

        clean_lines = [l.strip() for l in lines if l.strip()]
        if not clean_lines:
            continue

        # ── If ANY line is a heading, process line-by-line ────────────────
        # This handles mixed blocks like ["第1章", "### 序論", "body text…"]
        if any(_line_is_heading(l) for l in clean_lines):
            _lines_to_html_parts(clean_lines, parts)
            continue

        # ── Unordered list (all lines start with * or -) ──────────────────
        ul_m = [_UL_ITEM_RE.match(l) for l in clean_lines]
        if all(ul_m):
            items = ''.join(
                f'<li>{_md_inline(html.escape(m.group(1).strip()))}</li>'
                for m in ul_m
            )
            parts.append(f'<ul>{items}</ul>')
            continue

        # ── Ordered list (all lines start with N. or N)) ──────────────────
        ol_m = [_OL_ITEM_RE.match(l) for l in clean_lines]
        if all(ol_m):
            items = ''.join(
                f'<li>{_md_inline(html.escape(m.group(1).strip()))}</li>'
                for m in ol_m
            )
            parts.append(f'<ol>{items}</ol>')
            continue

        # ── Regular paragraph ─────────────────────────────────────────────
        parts.append(f'<p>{_md_inline(html.escape(" ".join(clean_lines)))}</p>')

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

    # Unwrap {"page_number": N, "text_blocks": [...]} format
    if isinstance(data, dict):
        if "text_blocks" in data:
            data = data["text_blocks"]
        else:
            return _plain_lines_to_html(str(data))

    if not isinstance(data, list):
        return _plain_lines_to_html(str(data))

    parts = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # Handle nested text_blocks per item
        if "text_blocks" in item:
            parts.extend(_json_block_to_html(_json.dumps(item["text_blocks"])))
            continue
        t = item.get("text_content") or item.get("text") or item.get("content", "")
        t = str(t).strip()
        if t:
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


_KATEX_HEAD = """\
<!-- KaTeX for fast LaTeX rendering -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body, {
    delimiters: [
      {left: '$$', right: '$$', display: true},
      {left: '$',  right: '$',  display: false}
    ],
    throwOnError: false
  });"></script>"""

# CSS for the single-page view.html (unchanged layout)
_PAGE_CSS = """\
  body { font-family: 'Noto Serif SC', Georgia, serif; max-width: 860px; margin: 2rem auto; padding: 0 1.2rem; line-height: 1.8; color: #1a1a1a; }
  h1 { font-size: 2rem; margin-bottom: 0.4rem; }
  h2 { font-size: 1.35rem; margin-top: 3rem; border-bottom: 1px solid #d0d0d0; padding-bottom: 0.3rem; }
  h3 { font-size: 1.1rem; margin-top: 1.8rem; }
  nav { background: #f6f6f6; padding: 1rem 1.2rem; border-radius: 6px; margin-bottom: 2.5rem; }
  nav ol { margin: 0; padding-left: 1.5rem; column-count: 2; }
  nav li { margin: 0.15rem 0; font-size: 0.9rem; }
  section { margin-bottom: 3rem; }
  p { margin: 0.7rem 0; text-align: justify; }
  ol, ul { margin: 0.5rem 0 0.5rem 1.5rem; }
  figure { margin: 1.8rem 0; text-align: center; }
  figure img { max-width: 100%; height: auto; border: 1px solid #e0e0e0; border-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }
  figcaption { font-size: 0.88rem; color: #666; margin-top: 0.5rem; font-style: italic; }
  .formula { margin: 1.2rem 0; text-align: center; overflow-x: auto; }
  .formula img { display: none; }
  .katex-display { margin: 0.8rem 0; }
  pre { background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; font-size: 0.9rem; }
  table { border-collapse: collapse; margin: 1.2rem 0; width: 100%; font-size: 0.92rem; }
  th, td { border: 1px solid #d0d0d0; padding: 0.5rem 0.8rem; text-align: left; }
  th { background: #f5f5f5; font-weight: 600; }
  tr:nth-child(even) td { background: #fafafa; }
  .ch-nav { display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0; border-top: 1px solid #e0e0e0; margin-top: 3rem; font-size: 0.9rem; }
  .ch-nav a { color: #b45309; text-decoration: none; }
  .ch-nav a:hover { text-decoration: underline; }
  .back-link { font-size: 0.85rem; color: #888; text-decoration: none; }
  .back-link:hover { color: #333; }
  .summary-text { font-size: 0.9rem; color: #555; margin: 0.3rem 0 0.8rem; }"""

# CSS for the sidebar-based chapter site
_SIDEBAR_CSS = """\
  *, *::before, *::after { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; }
  body { font-family: 'Noto Serif SC', Georgia, serif; color: #1a1a1a; background: #fafaf8; }

  /* ── Sidebar ─────────────────────────────────────────── */
  .sidebar {
    position: fixed; left: 0; top: 0;
    width: 248px; height: 100vh;
    background: #f5f2ed; border-right: 1px solid #e2ddd6;
    overflow-y: auto; padding: 1.4rem 1rem 2.5rem;
    font-size: 0.82rem; line-height: 1.45;
  }
  .sidebar-title {
    font-weight: 700; font-size: 0.9rem; color: #1a1a1a;
    line-height: 1.4; margin-bottom: 1.2rem; padding-bottom: 0.9rem;
    border-bottom: 1px solid #d9d4cc;
  }
  .sidebar-title a { color: inherit; text-decoration: none; }
  .sidebar-title a:hover { color: #b45309; }
  .toc-label {
    font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.07em;
    color: #aaa; margin-bottom: 0.35rem;
  }
  .toc-list { list-style: none; margin: 0 0 1rem; padding: 0; }
  .toc-list li { margin: 0; }
  .toc-list a {
    display: block; padding: 0.28rem 0.55rem; border-radius: 5px;
    color: #5a5550; text-decoration: none; transition: background .13s, color .13s;
  }
  .toc-list a:hover { background: #ebe7e0; color: #1a1a1a; }
  .toc-list a.active { background: #fef3c7; color: #b45309; font-weight: 600; }
  .sidebar-sep { border: none; border-top: 1px solid #d9d4cc; margin: 0.9rem 0; }
  .sidebar-extra a {
    display: block; padding: 0.28rem 0.55rem; border-radius: 5px;
    color: #5a5550; text-decoration: none; transition: background .13s;
  }
  .sidebar-extra a:hover { background: #ebe7e0; color: #1a1a1a; }
  .sidebar-extra a.active { color: #b45309; font-weight: 600; }

  /* ── Main content ────────────────────────────────────── */
  .content {
    margin-left: 248px; padding: 2.8rem 3.2rem 5rem;
    max-width: 860px; min-height: 100vh;
  }
  h1 { font-size: 1.85rem; margin: 0 0 0.5rem; line-height: 1.3; }
  h2 { font-size: 1.3rem; margin: 2.5rem 0 0.7rem; border-bottom: 1px solid #e2ddd6; padding-bottom: 0.3rem; }
  h3 { font-size: 1.05rem; margin: 1.8rem 0 0.5rem; }
  p { margin: 0.7rem 0; text-align: justify; line-height: 1.85; }
  ol, ul { margin: 0.5rem 0 0.5rem 1.5rem; line-height: 1.8; }
  figure { margin: 1.9rem 0; text-align: center; }
  figure img { max-width: 100%; height: auto; border: 1px solid #e0dbd5; border-radius: 4px; box-shadow: 0 1px 5px rgba(0,0,0,.09); }
  figcaption { font-size: 0.87rem; color: #777; margin-top: 0.5rem; font-style: italic; }
  pre { background: #f5f3ef; padding: 1rem; border-radius: 5px; overflow-x: auto; font-size: 0.89rem; }
  table { border-collapse: collapse; margin: 1.3rem 0; width: 100%; font-size: 0.9rem; }
  th, td { border: 1px solid #d9d4cc; padding: 0.5rem 0.85rem; text-align: left; }
  th { background: #ede9e2; font-weight: 600; }
  tr:nth-child(even) td { background: #faf8f5; }
  .katex-display { margin: 0.8rem 0; }

  /* ── Chapter navigation ──────────────────────────────── */
  .ch-nav {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.9rem 0; border-top: 1px solid #e2ddd6; margin-top: 3.5rem; font-size: 0.88rem;
  }
  .ch-nav a { color: #b45309; text-decoration: none; }
  .ch-nav a:hover { text-decoration: underline; }

  /* ── Index page ──────────────────────────────────────── */
  .book-header { margin-bottom: 2.5rem; }
  .book-header h1 { font-size: 2rem; margin-bottom: 0.3rem; }
  .toc-index { list-style: none; margin: 0; padding: 0; }
  .toc-index > li { border-bottom: 1px solid #ede8e1; padding: 0.9rem 0; }
  .toc-index > li:last-child { border-bottom: none; }
  .toc-index a { font-weight: 600; color: #1a1a1a; text-decoration: none; font-size: 0.97rem; }
  .toc-index a:hover { color: #b45309; }
  .toc-index .ch-num { color: #aaa; font-size: 0.8rem; font-weight: 400; margin-right: 0.4rem; }
  .toc-index .summary {
    font-size: 0.86rem; color: #777; margin-top: 0.3rem; line-height: 1.6;
    max-height: 7.5rem; overflow: hidden;
    mask-image: linear-gradient(to bottom, black 55%, transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, black 55%, transparent 100%);
  }
  .toc-index .summary p { margin: 0 0 0.4em; }
  .toc-index .summary ul, .toc-index .summary ol { margin: 0; padding-left: 1.3em; }
  .toc-index .summary table { font-size: inherit; border-collapse: collapse; width: 100%; }
  .toc-index .summary td, .toc-index .summary th { padding: 0.12em 0.5em; border: 1px solid #ddd; }

  /* ── Figures page ────────────────────────────────────── */
  .fig-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1.2rem; margin-top: 1.5rem;
  }
  .fig-card { border: 1px solid #e2ddd6; border-radius: 6px; overflow: hidden; background: #fff; }
  .fig-card img { width: 100%; height: 150px; object-fit: cover; display: block; }
  .fig-card .fig-caption { padding: 0.55rem 0.7rem; font-size: 0.82rem; color: #555; line-height: 1.4; }
  .fig-card .fig-id { font-size: 0.7rem; color: #aaa; font-family: monospace; margin-bottom: 0.2rem; }

  /* ── Responsive ──────────────────────────────────────── */
  @media (max-width: 720px) {
    .sidebar {
      position: static; width: 100%; height: auto;
      border-right: none; border-bottom: 1px solid #e2ddd6;
    }
    .content { margin-left: 0; padding: 1.5rem 1.2rem 3rem; }
  }"""

# Inline JS to highlight the active sidebar link by matching the current filename
_ACTIVE_JS = """\
<script>
(function(){
  var p = window.location.pathname.split('/').pop() || 'index.html';
  if (!p || p === '') p = 'index.html';
  document.querySelectorAll('.toc-list a, .sidebar-extra a').forEach(function(a){
    var h = (a.getAttribute('href') || '').replace(/.*\\//, '');
    if (h === p) a.classList.add('active');
  });
})();
</script>"""


def _figure_html(img: ImageRecord, img_path_prefix: str) -> str:
    desc = html.escape(img.description or img.filename)
    return (
        f'<figure>'
        f'<img src="{img_path_prefix}{img.filename}" alt="{desc}" loading="lazy">'
        f'<figcaption>{desc}</figcaption>'
        f'</figure>'
    )


def _interleave_text_images(
    text: str,
    images_by_page: dict[int, list[ImageRecord]],
    img_path_prefix: str = "images/",
) -> str:
    """Render chapter text with figures inserted at their originating page positions.

    Requires [[PAGE:N]] markers in *text* (written by pipeline since this feature
    was added).  Falls back to images-first layout for older text files without markers.
    """
    if not _PAGE_MARKER_RE.search(text):
        # Older format without markers: put all images at top, then text
        img_html = "\n".join(
            _figure_html(img, img_path_prefix)
            for imgs in images_by_page.values()
            for img in imgs
        )
        return (img_html + "\n" if img_html else "") + _chapter_text_to_html(text)

    parts: list[str] = []
    # split() with a capturing group interleaves [text, pagenum, text, pagenum, ...]
    segments = _PAGE_MARKER_RE.split(text)
    # segments[0] — text before first PAGE marker (usually empty)
    if segments[0].strip():
        parts.append(_chapter_text_to_html(segments[0]))

    i = 1
    while i < len(segments) - 1:
        page_num = int(segments[i])
        seg_text = segments[i + 1]
        for img in images_by_page.get(page_num, []):
            parts.append(_figure_html(img, img_path_prefix))
        if seg_text.strip():
            parts.append(_chapter_text_to_html(seg_text))
        i += 2

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

        ch_images = {p: v for p, v in images_by_page.items() if ch.start_page <= p < ch.end_page}

        section_parts = [f'<section id="ch-{ch.index}">']
        section_parts.append(f"<h2>{html.escape(ch.title)}</h2>")
        section_parts.append(_interleave_text_images(ch_text, ch_images, "images/"))
        section_parts.append("</section>")
        sections.append("\n".join(section_parts))

    toc_items = "".join(
        f'<li><a href="#ch-{ch.index}">{html.escape(ch.title)}</a></li>'
        for ch in chapters
    )

    body = "\n\n".join(sections)
    title_esc = html.escape(book_title)

    return (
        f'<!DOCTYPE html>\n<html lang="zh">\n<head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{title_esc}</title>\n'
        f'{_KATEX_HEAD}\n'
        f'<style>\n{_PAGE_CSS}\n</style>\n'
        f'</head>\n<body>\n'
        f'<h1>{title_esc}</h1>\n'
        f'<nav>\n  <ol>{toc_items}</ol>\n</nav>\n\n'
        f'{body}\n'
        f'</body>\n</html>'
    )


def build_chapter_site(
    book_title: str,
    chapters: list[Chapter],
    images: list[ImageRecord],
    text_dir: Path,
) -> dict[str, str]:
    """Return {filename: html_content} for the per-chapter book site.

    Files produced:
      index.html        — overview / TOC with summaries
      ch_NN.html        — one page per chapter with sidebar navigation
      figures.html      — figure index grid (only if images exist)

    All image paths are relative (../images/…) so files work identically
    when served by the API and when opened from a ZIP export offline.
    """
    images_by_page: dict[int, list[ImageRecord]] = {}
    for img in images:
        images_by_page.setdefault(img.page, []).append(img)

    has_figures = bool(images)
    title_esc = html.escape(book_title)
    ch_filenames = {ch.index: f"ch_{ch.index:02d}.html" for ch in chapters}

    def _head(page_title: str) -> str:
        return (
            f'<!DOCTYPE html>\n<html lang="und">\n<head>\n'
            f'<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{html.escape(page_title)}</title>\n'
            f'{_KATEX_HEAD}\n'
            f'<style>\n{_SIDEBAR_CSS}\n</style>\n'
            f'</head>\n<body>\n'
        )

    def _sidebar() -> str:
        toc_items = "".join(
            f'<li><a href="{ch_filenames[ch.index]}">{html.escape(ch.title)}</a></li>'
            for ch in chapters
        )
        figs_section = ""
        if has_figures:
            figs_section = (
                '<hr class="sidebar-sep">'
                '<div class="sidebar-extra">'
                f'<a href="figures.html">&#9634; Figures ({len(images)})</a>'
                '</div>'
            )
        return (
            '<nav class="sidebar">'
            f'<div class="sidebar-title"><a href="index.html">{title_esc}</a></div>'
            '<div class="toc-label">Contents</div>'
            '<ol class="toc-list">'
            '<li><a href="index.html">Overview</a></li>'
            f'{toc_items}'
            '</ol>'
            f'{figs_section}'
            '</nav>'
        )

    files: dict[str, str] = {}

    # ── Per-chapter pages ─────────────────────────────────────────────────────
    for i, ch in enumerate(chapters):
        ch_file = text_dir / f"ch_{ch.index:02d}.txt"
        ch_text = ch_file.read_text(encoding="utf-8") if ch_file.exists() else ""
        ch_images = {p: v for p, v in images_by_page.items() if ch.start_page <= p < ch.end_page}
        ch_title_esc = html.escape(ch.title)
        fn = ch_filenames[ch.index]

        prev_link = (
            f'<a href="{ch_filenames[chapters[i-1].index]}">← {html.escape(chapters[i-1].title)}</a>'
            if i > 0 else '<span></span>'
        )
        next_link = (
            f'<a href="{ch_filenames[chapters[i+1].index]}">{html.escape(chapters[i+1].title)} →</a>'
            if i < len(chapters) - 1 else '<span></span>'
        )

        body = (
            f'{_sidebar()}'
            f'<div class="content">'
            f'<h1>{ch_title_esc}</h1>'
            f'{_interleave_text_images(ch_text, ch_images, "../images/")}'
            f'<div class="ch-nav">{prev_link}{next_link}</div>'
            f'</div>'
            f'{_ACTIVE_JS}'
            f'</body>\n</html>'
        )
        files[fn] = _head(f"{ch.title} — {book_title}") + body

    # ── Index / overview page ─────────────────────────────────────────────────
    toc_entries = []
    for idx, ch in enumerate(chapters):
        summary_file = text_dir / f"ch_{ch.index:02d}_summary.txt"
        summary = summary_file.read_text(encoding="utf-8").strip() if summary_file.exists() else ""
        fn = ch_filenames[ch.index]
        ch_title_esc = html.escape(ch.title)
        summary_html = ""
        if summary:
            rendered = "".join(_plain_lines_to_html(summary))
            summary_html = f'<div class="summary">{rendered}</div>'
        toc_entries.append(
            f'<li>'
            f'<a href="{fn}"><span class="ch-num">Ch.{idx + 1}</span>{ch_title_esc}</a>'
            f'{summary_html}'
            f'</li>'
        )

    figs_link_html = (
        f'<p style="margin-bottom:1.8rem">'
        f'<a href="figures.html" style="color:#b45309;text-decoration:none;font-size:0.9rem;">'
        f'&#9634; Figure Index &mdash; {len(images)} figures</a></p>'
        if has_figures else ""
    )

    index_body = (
        f'{_sidebar()}'
        f'<div class="content">'
        f'<div class="book-header"><h1>{title_esc}</h1></div>'
        f'{figs_link_html}'
        f'<ol class="toc-index">{"".join(toc_entries)}</ol>'
        f'</div>'
        f'{_ACTIVE_JS}'
        f'</body>\n</html>'
    )
    files["index.html"] = _head(book_title) + index_body

    # ── Figures index page ────────────────────────────────────────────────────
    if has_figures:
        fig_cards = []
        fig_num = 0
        for page_num in sorted(images_by_page.keys()):
            for img in images_by_page[page_num]:
                fig_num += 1
                fig_id = f"fig-{fig_num:03d}"
                desc = html.escape(img.description or img.filename)
                fig_cards.append(
                    f'<div class="fig-card" id="{fig_id}">'
                    f'<img src="../images/{img.filename}" alt="{desc}" loading="lazy">'
                    f'<div class="fig-caption">'
                    f'<div class="fig-id">{fig_id} · p.{page_num + 1}</div>'
                    f'{desc}'
                    f'</div>'
                    f'</div>'
                )

        figs_body = (
            f'{_sidebar()}'
            f'<div class="content">'
            f'<h1>Figure Index</h1>'
            f'<p style="color:#777;font-size:0.9rem">{fig_num} figure{"s" if fig_num != 1 else ""} extracted.</p>'
            f'<div class="fig-grid">{"".join(fig_cards)}</div>'
            f'</div>'
            f'{_ACTIVE_JS}'
            f'</body>\n</html>'
        )
        files["figures.html"] = _head(f"Figures — {book_title}") + figs_body

    return files
