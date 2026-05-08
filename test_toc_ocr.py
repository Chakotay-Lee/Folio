"""
Test: Post-processing approach for TOC page detection and extraction.

Runs standard OCR (no TOC instructions in prompt), then applies regex post-processing
to detect and extract TOC entries from both pages, combining them into one table.

Usage:
    python3 test_toc_ocr.py [page_numbers...]

Default: tests pages 5, 6 (0-based) of the quantum optics book.
"""
import re
import sys
import io
import base64
import httpx
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
PDF_PATH = Path("/Users/alexlee/Documents/Books/科學/物理學/量子光學/量子光學原理---張勇.pdf")
PAGES = [int(a) for a in sys.argv[1:]] or [5, 6]   # 0-based page numbers

sys.path.insert(0, str(Path(__file__).parent))
from backend.config_loader import load_config
cfg = load_config()
am = cfg.llms.analysis_model or cfg.llms.extraction_model
BASE_URL = am.base_url.rstrip("/")
API_KEY  = am.api_key or ""
MODEL    = am.model_name
TIMEOUT  = am.timeout_seconds

# ── Standard OCR prompt (unchanged — no TOC hint) ────────────────────────────
OCR_PROMPT = """\
CRITICAL: ALL mathematical expressions — including single variables with \
subscripts/superscripts — MUST be wrapped in LaTeX delimiters. \
Inline math: $formula$  (e.g. $A_H$, $\\frac{\\partial f}{\\partial t}$). \
Display math on its own line: $$formula$$  (e.g. $$E = mc^2$$). \
Never write raw LaTeX commands (\\frac, \\alpha, \\left, etc.) outside $ delimiters.
Extract all text from this page verbatim. \
Output plain text + LaTeX only — no HTML tags, no markdown code fences.
STRUCTURE RULES:
- Chapter/section headings (visually larger, bold, or numbered like '1.2 Title' / '第N章'): \
prefix with ## (top-level section) or ### (subsection).
- Tables: use markdown pipe format with a separator row.
- Blank line before and after each heading and table.
"""

# ── TOC post-processor ────────────────────────────────────────────────────────
def extract_toc_entries(text: str) -> list[tuple[str, str]] | None:
    """
    Try to extract TOC entries regardless of output format.

    Handles three formats the LLM might produce:
      1. markdown table row  : | 4.2.5 相干態 | 40 |
      2. LaTeX cdots format  : 4.2.5 相干態 $\\cdots \\cdots 40$
      3. plain dots format   : 4.2.5 相干態 ………… 40

    Returns list of (title, page_num) pairs if >35% of lines match, else None.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    entries: list[tuple[str, str]] = []
    content_lines = 0

    for line in lines:
        # Skip pure separator / alignment rows
        if re.match(r'^[\s|:\-]+$', line):
            continue
        content_lines += 1

        # Format 1: markdown table row  | title | number |
        m = re.match(r'^\|\s*(.+?)\s*\|\s*(\d+)\s*\|?\s*$', line)
        if m and not re.match(r'^[:*\-\s]+$', m.group(1)):
            entries.append((m.group(1).strip(), m.group(2)))
            continue

        # Format 2: LaTeX  title $\cdots ... N$
        m = re.match(r'^(.+?)\s*\$[\s\\cdots\.·…]+(\d+)\s*\$\s*$', line)
        if m:
            entries.append((m.group(1).strip(), m.group(2)))
            continue

        # Format 3: plain dots  title ……… N  (or ...N)
        m = re.match(r'^(.+?)\s*[·\.…]{3,}\s*(\d+)\s*$', line)
        if m:
            entries.append((m.group(1).strip(), m.group(2)))
            continue

    if content_lines == 0:
        return None
    ratio = len(entries) / content_lines
    return entries if (len(entries) >= 4 and ratio > 0.35) else None


def entries_to_markdown(entries: list[tuple[str, str]]) -> str:
    rows = ["| 章節 | 頁碼 |", "| --- | --- |"]
    for title, page in entries:
        rows.append(f"| {title} | {page} |")
    return "\n".join(rows)

# ── Helpers ───────────────────────────────────────────────────────────────────
def render_page(pdf_path: Path, page_num: int):
    import fitz
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    from PIL import Image
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    doc.close()
    return img


def img_to_b64(img) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def call_vlm(img_b64: str, prompt: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        "max_tokens": 2048,
        "temperature": 0.1,
    }
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    resp = httpx.post(f"{BASE_URL}/chat/completions", json=payload,
                      headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


# ── Main ──────────────────────────────────────────────────────────────────────
print(f"Model : {MODEL}")
print(f"PDF   : {PDF_PATH.name}")
print(f"Pages : {PAGES}  (0-based)\n")
print("=" * 70)

all_entries: list[tuple[str, str]] = []

for pnum in PAGES:
    print(f"\n── Page {pnum} ──────────────────────────────────────────────────────")
    img = render_page(PDF_PATH, pnum)
    b64 = img_to_b64(img)
    print("   calling VLM…")
    raw = call_vlm(b64, OCR_PROMPT)

    print("\n[RAW VLM OUTPUT]")
    print(raw[:800], "…" if len(raw) > 800 else "")

    entries = extract_toc_entries(raw)
    if entries:
        print(f"\n[POST-PROCESSED] detected as TOC — {len(entries)} entries, skip figure detection")
        all_entries.extend(entries)
    else:
        ratio = 0
        print(f"\n[POST-PROCESSED] NOT detected as TOC (ratio too low)")

print("\n" + "=" * 70)
if all_entries:
    print(f"\n[COMBINED TOC TABLE — {len(all_entries)} entries total]\n")
    print(entries_to_markdown(all_entries))
else:
    print("\nNo TOC entries detected across all pages.")
