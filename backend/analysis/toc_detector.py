"""Post-processing TOC page detection.

Two-strategy approach:

  Strategy 1 — Dot-leader scan (re.findall across full text):
    Handles dense/concatenated formats where multiple entries sit on one line.
    Recognises any of: · . … ・(U+30FB) and 3+ repetitions as a leader.
    e.g.  4.2.5 title dot-dot-dot 40  4.2.6 title2 dot-dot 42

  Strategy 2 — Per-block matching (blank-line separated blocks):
    Handles LLM-formatted output where each entry is its own block.
    Formats: markdown table row | LaTeX cdots | dot leader | inline number | title+newline+N

Heading prefixes (####, ##, #) are stripped before matching.
Threshold: >= 4 entries from either strategy.
"""
from __future__ import annotations
import re

# ── Shared helpers ─────────────────────────────────────────────────────────────
_HEADING_PREFIX_RE = re.compile(r'^#{1,6}\s+')
_STANDALONE_NUM_RE = re.compile(r'^\d+\s*$')
_TRAILING_NUM_RE   = re.compile(r'^(.+?)\s+(\d{1,4})\s*$')
_MDROW_RE          = re.compile(r'^\|\s*(.+?)\s*\|\s*(\d+)\s*\|?\s*$')
_LATEX_CDOTS_RE    = re.compile(r'^(.+?)\s*\$[\s\\cdots\.·…]+(\d+)\s*\$\s*$')
_SEP_RE            = re.compile(r'^[\s|:\-]+$')

# Dot-leader characters: ASCII period, · (U+00B7), ・ (U+30FB), … (U+2026)
_DOT_CHARS = r'[·\.…・·・…]'
_DOTS_RE   = re.compile(rf'^(.+?)\s*{_DOT_CHARS}{{3,}}\s*(\d{{1,3}})\s*$')

# ── Strategy 1: global dot-leader scan ────────────────────────────────────────
# Finds "section/chapter heading + title + dots + page" anywhere in full text.
# Works even when multiple entries are concatenated on a single line.
_DOT_SCAN_RE = re.compile(
    # section/chapter number + title (no dot chars, no newline) + dot leader + page
    r'((?:\d+(?:\.\d+)*|第\s*\d+\s*[章節节篇部])\s+[^\n·・…\.]{2,}?)'
    rf'\s*{_DOT_CHARS}{{3,}}\s*'
    r'(\d{1,3})'
    r'(?=\s|$|[^\d])'   # not immediately followed by another digit
)


def _clean_title(s: str) -> str:
    s = _HEADING_PREFIX_RE.sub('', s)
    s = s.lstrip('#').strip()
    return re.sub(r'\s+', ' ', s)


def _scan_dot_entries(text: str) -> list[tuple[str, str]]:
    """Strategy 1: scan entire text for dot-leader TOC entries."""
    results: list[tuple[str, str]] = []
    for m in _DOT_SCAN_RE.finditer(text):
        title = _clean_title(m.group(1))
        if title:
            results.append((title, m.group(2)))
    return results


# ── Strategy 2: per-block matching ────────────────────────────────────────────

def _extract_block_entries(text: str) -> list[tuple[str, str]] | None:
    """Strategy 2: process blank-line-separated blocks individually."""
    blocks = [b.strip() for b in re.split(r'\n{2,}', text.strip()) if b.strip()]
    entries: list[tuple[str, str]] = []

    for block in blocks:
        lines = [_clean_title(l) for l in block.splitlines()]
        lines = [l for l in lines if l and not _SEP_RE.match(l)]
        if not lines:
            continue

        matched = False

        # Format A: markdown table row
        if len(lines) == 1:
            m = _MDROW_RE.match(lines[0])
            if m and not re.match(r'^[:*\-\s]+$', m.group(1)):
                entries.append((_clean_title(m.group(1)), m.group(2)))
                matched = True

        # Formats B/C: LaTeX cdots or dot leader — process ALL matching lines in block
        # (handles both single-entry blocks and multi-entry adjacent-line blocks)
        if not matched:
            for line in lines:
                m = _LATEX_CDOTS_RE.match(line)
                if m:
                    entries.append((_clean_title(m.group(1)), m.group(2)))
                    matched = True
                    continue
                m = _DOTS_RE.match(line)
                if m:
                    entries.append((_clean_title(m.group(1)), m.group(2)))
                    matched = True

        # Format E: title on first lines, standalone number on last line
        if not matched and _STANDALONE_NUM_RE.match(lines[-1]) and len(lines) >= 2:
            title = ' '.join(lines[:-1])
            title = _clean_title(title)
            if title and not re.match(r'^[\s\d\.]+$', title):
                entries.append((title, lines[-1].strip()))
                matched = True

        # Format D: entire block joined, trailing number (handles "Title 89" inline)
        if not matched:
            full = _clean_title(' '.join(lines))
            m = _TRAILING_NUM_RE.match(full)
            if m:
                title = _clean_title(m.group(1))
                num   = m.group(2)
                if 1 <= int(num) <= 999 and title and not re.match(r'^[\d\.\s]+$', title):
                    entries.append((title, num))

    if not blocks:
        return None
    ratio = len(entries) / len(blocks)
    return entries if (len(entries) >= 4 and ratio > 0.35) else None


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_toc_entries(text: str) -> list[tuple[str, str]] | None:
    """Return (title, page_num) pairs if the text looks like a TOC, else None.

    Runs both strategies and returns the result with more entries:
    - Strategy 1 (dot scan) catches dense/concatenated formats but only numbered headings.
    - Strategy 2 (per-block) catches all headings including unnumbered (序論, まとめ, etc.).
    """
    dot_entries  = _scan_dot_entries(text)
    block_entries = _extract_block_entries(text)

    candidates = [e for e in (dot_entries, block_entries) if e and len(e) >= 4]
    if not candidates:
        return None
    # Prefer the result with more entries (block matching is more complete)
    return max(candidates, key=len)


_TOC_HEADER_RE = re.compile(
    r'目\s*[录録次]|CONTENTS|TABLE\s+OF\s+CONTENTS', re.IGNORECASE
)


def is_toc_page(text: str) -> bool:
    """Return True if the page looks like a TOC even if entries can't be parsed.

    Catches cases where the VLM enters a dot-repetition loop: the header is still
    present in the first few hundred characters but the entry numbers are buried
    far beyond where regex can reliably find them.
    """
    if not _TOC_HEADER_RE.search(text[:500]):
        return False
    # Must have substantial dot-leader content (≥30 dot characters)
    dot_count = text.count('・') + text.count('…') + text.count('·') + text.count('.')
    return dot_count >= 30


def entries_to_markdown_table(entries: list[tuple[str, str]]) -> str:
    rows = ["| 章節 | 頁碼 |", "| --- | --- |"]
    for title, page in entries:
        rows.append(f"| {title} | {page} |")
    return "\n".join(rows)
