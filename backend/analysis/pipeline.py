"""Background analysis pipeline orchestrator."""
from __future__ import annotations
import json as _json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CODE_BLOCK_RE = re.compile(r'```(\w*)\s*\n(.*?)\n```', re.DOTALL)
_BODY_RE = re.compile(r'<body>(.*?)</body>', re.DOTALL | re.IGNORECASE)

# ── Cross-page paragraph joining ──────────────────────────────────────────────
_PAGE_SPLIT_RE  = re.compile(r'\[\[PAGE:(\d+)\]\]\n?')
# Sentence-ending punctuation (CJK + Latin)
_SENT_END_RE    = re.compile(r'[.。!！?？…」』\)\）]+\s*$')
# Structural block starters — never merge these with the previous page
_NEW_BLOCK_RE   = re.compile(r'^(#{1,6}\s|[-*•]\s|\d+[.)]\s|\|)')


def _join_cross_page_paragraphs(text: str) -> str:
    """Stitch paragraphs that were split at page boundaries.

    When page N ends mid-sentence, the continuation (first paragraph of page
    N+1) is moved *before* the [[PAGE:N+1]] marker so:
    - html_builder renders a complete paragraph inside page N's segment
    - the [[PAGE:N+1]] anchor stays in place for image injection
    - ch_XX.txt / chat context reads as coherent prose

    Handles English end-of-line hyphenation (``word-`` → ``word``).
    Does NOT touch boundaries where the previous page ends with sentence
    punctuation or where the next page starts a heading / list / table.
    """
    parts = _PAGE_SPLIT_RE.split(text)
    # parts = [pre, num1, seg1, num2, seg2, ...]
    if len(parts) < 5:          # fewer than 2 page markers — nothing to join
        return text

    pre = parts[0]
    segs: list[list[str]] = []
    i = 1
    while i + 1 < len(parts):
        segs.append([parts[i], parts[i + 1]])
        i += 2

    for idx in range(len(segs) - 1):
        prev_seg = segs[idx][1]
        next_seg = segs[idx + 1][1]

        prev_nonempty = [l for l in prev_seg.rstrip().splitlines() if l.strip()]
        next_stripped  = next_seg.lstrip('\n')
        next_nonempty  = [l for l in next_stripped.splitlines() if l.strip()]

        if not prev_nonempty or not next_nonempty:
            continue

        last  = prev_nonempty[-1].rstrip()
        first = next_nonempty[0].lstrip()

        if _SENT_END_RE.search(last):   # sentence completed → no join
            continue
        if _NEW_BLOCK_RE.match(first):  # new structural element → no join
            continue

        # Isolate the first paragraph of next_seg (up to first blank line)
        double_nl = next_stripped.find('\n\n')
        if double_nl == -1:
            first_para, rest = next_stripped.rstrip(), ''
        else:
            first_para = next_stripped[:double_nl]
            rest = next_stripped[double_nl + 2:]

        # Join with space (or directly if prev line is hyphenated)
        prev_body = prev_seg.rstrip('\n').rstrip()
        if prev_body.endswith('-'):
            joined = prev_body[:-1] + first_para
        else:
            joined = prev_body + ' ' + first_para

        segs[idx][1]     = joined + '\n'
        segs[idx + 1][1] = (rest + '\n') if rest.strip() else '\n'

    out = pre
    for num, seg in segs:
        out += f'[[PAGE:{num}]]\n{seg}'
    return out

# ── LaTeX auto-wrap ────────────────────────────────────────────────────────────
_MATH_PROT_RE = re.compile(r'\$\$[\s\S]*?\$\$|\$[^\n$]+?\$')
# Match contiguous ASCII "math chars" (CJK acts as natural boundary)
_MATH_ASCII_SEG_RE = re.compile(r'[A-Za-z0-9 \\{}\[\]()_^=+\-<>.,!|*/]+')


def _auto_wrap_latex(text: str) -> str:
    """Wrap bare LaTeX backslash commands in $...$ if not already wrapped.

    Splits on CJK character boundaries; only wraps ASCII segments that contain
    at least one backslash command (\\cmd).  Already-wrapped $...$ regions are
    protected and left untouched.
    """
    protected: list[str] = []

    def _prot(m: re.Match) -> str:
        n = len(protected)
        protected.append(m.group(0))
        return f'\x02{n:04d}\x02'

    t = _MATH_PROT_RE.sub(_prot, text)

    def _maybe_wrap(m: re.Match) -> str:
        s = m.group(0)
        if '\\' not in s:
            return s
        stripped = s.strip()
        if not stripped:
            return s
        lead  = s[:len(s) - len(s.lstrip())]
        trail = s[len(s.rstrip()):]
        return f'{lead}${stripped}${trail}'

    t = _MATH_ASCII_SEG_RE.sub(_maybe_wrap, t)

    for n, v in enumerate(protected):
        t = t.replace(f'\x02{n:04d}\x02', v)
    return t


def _normalize_ocr_text(raw: str) -> str:
    """Normalize VLM OCR output to plain text + LaTeX.

    Models often wrap output in ```json, ```html, or plain ``` blocks despite
    instructions to the contrary.  This function extracts the actual text so
    that both html_builder and chat_context get clean content.

    - ```html blocks: kept as-is (html_builder will parse them for structure)
    - ```json blocks: text_content / text / content fields extracted
    - plain ``` blocks: try JSON extraction, fall back to literal text
    - plain text: kept as-is
    """
    parts: list[str] = []
    last_end = 0

    for m in _CODE_BLOCK_RE.finditer(raw):
        lang = m.group(1).lower()
        block = m.group(2)

        before = raw[last_end:m.start()].strip()
        if before:
            parts.append(before)

        if lang == "html":
            parts.append(m.group(0))          # keep full fence for html_builder
        elif lang == "json" or lang == "":
            try:
                data = _json.loads(block)
            except _json.JSONDecodeError:
                fixed = re.sub(r'\\(?!["\\])', r'\\\\', block)
                try:
                    data = _json.loads(fixed)
                except _json.JSONDecodeError:
                    data = None

            # Unwrap {"page_number": N, "text_blocks": [...]} format
            if isinstance(data, dict) and "text_blocks" in data:
                data = data["text_blocks"]

            if isinstance(data, list):
                texts = []
                for item in data:
                    if isinstance(item, dict):
                        if "text_blocks" in item:
                            for tb in item["text_blocks"]:
                                if isinstance(tb, dict):
                                    t = tb.get("text_content") or tb.get("text") or tb.get("content", "")
                                    if t:
                                        texts.append(str(t).strip())
                        else:
                            t = item.get("text_content") or item.get("text") or item.get("content", "")
                            if t:
                                texts.append(str(t).strip())
                if texts:
                    parts.append("\n\n".join(texts))
                else:
                    parts.append(block)
            else:
                parts.append(block)
        else:
            parts.append(block)

        last_end = m.end()

    remaining = raw[last_end:].strip()
    if remaining:
        parts.append(remaining)

    result = "\n\n".join(p for p in parts if p.strip())
    return _auto_wrap_latex(result)

# ── Job registry (in-memory) ──────────────────────────────────────────────────

@dataclass
class AnalysisJob:
    book_uuid: str
    status: str = "queued"          # queued | analyzing | done | failed
    current_page: int = 0
    total_pages: int = 0
    started_at: float = field(default_factory=time.time)
    stage: str = "queued"
    error: str = ""
    cancelled: bool = False
    _page_times: list[float] = field(default_factory=list, repr=False)

    def record_page(self) -> None:
        self._page_times.append(time.time())

    def eta_seconds(self) -> float | None:
        if len(self._page_times) < 3 or self.total_pages == 0:
            return None
        elapsed = self._page_times[-1] - self._page_times[0]
        avg = elapsed / len(self._page_times)
        remaining = self.total_pages - self.current_page
        return round(avg * remaining, 1)


@dataclass
class AnalysisOptions:
    """Per-analysis overrides passed from the frontend trigger request."""
    language: str = ""              # "" = auto; "zh-TW", "zh-CN", "en", "ja", …
    extra_prompt: str = ""          # appended to OCR and summary prompts
    analysis_model: dict | None = None   # overrides cfg.llms.analysis_model
    extraction_model: dict | None = None # overrides cfg.llms.extraction_model
    page_start: int | None = None   # 0-based inclusive; None = from beginning
    page_end: int | None = None     # 0-based exclusive; None = to end
    mode: str = "full"              # "full" | "quick" (skip figure detection)

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisOptions":
        return cls(
            language=d.get("language", ""),
            extra_prompt=d.get("extra_prompt", ""),
            analysis_model=d.get("analysis_model") or None,
            extraction_model=d.get("extraction_model") or None,
            page_start=d.get("page_start"),
            page_end=d.get("page_end"),
            mode=d.get("mode", "full"),
        )


_jobs: dict[str, AnalysisJob] = {}
_lock = threading.Lock()


def get_job(book_uuid: str) -> AnalysisJob | None:
    with _lock:
        return _jobs.get(book_uuid)


def register_job(job: AnalysisJob) -> None:
    with _lock:
        _jobs[job.book_uuid] = job


# ── Pipeline ──────────────────────────────────────────────────────────────────

def _build_provider(opts_model: dict, fallback_cfg):
    """Build an LLMProvider from an options override dict, merging with fallback config."""
    from backend.config_loader import LLMModelConfig
    from backend.llm.factory import get_provider as _get_provider
    merged = LLMModelConfig(
        provider=opts_model.get("provider", fallback_cfg.provider),
        model_name=opts_model.get("model_name", fallback_cfg.model_name),
        base_url=opts_model.get("base_url", fallback_cfg.base_url),
        api_key=opts_model.get("api_key", fallback_cfg.api_key),
        temperature=float(opts_model.get("temperature", fallback_cfg.temperature)),
        max_tokens=int(opts_model.get("max_tokens", fallback_cfg.max_tokens)),
        timeout_seconds=int(opts_model.get("timeout_seconds", fallback_cfg.timeout_seconds)),
    )
    return _get_provider(merged)


def run_analysis(book_uuid: str, pdf_path: Path, cfg, opts: AnalysisOptions | None = None) -> None:
    """Main pipeline: runs in a background thread."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.analysis.chapter_detector import detect_chapters
    from backend.analysis.image_extractor import (
        extract_native_images, extract_scanned_images, describe_image, ImageRecord
    )
    from backend.analysis.summarizer import summarize_chapter
    from backend.analysis.html_builder import build_view_html, build_chapter_site
    from backend.analysis.manifest import init_manifest, update_manifest_page, finalize_manifest
    from backend.analysis.toc_detector import (
            extract_toc_entries, entries_to_markdown_table, is_toc_page as _is_toc_hdr,
        )
    from backend.llm.factory import get_provider
    from sqlmodel import select

    if opts is None:
        opts = AnalysisOptions()

    job = get_job(book_uuid)
    if job is None:
        return

    analysis_dir = cfg.analysis_dir / book_uuid
    text_dir = analysis_dir / "text"
    images_dir = analysis_dir / "images"
    text_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    def set_status(status: str) -> None:
        job.status = status
        job.stage = status
        _update_book_status(book_uuid, status)

    try:
        import fitz
    except ImportError:
        log.error("PyMuPDF not installed — cannot run analysis")
        job.status = "failed"
        job.error = "PyMuPDF not installed"
        set_status("failed")
        return

    try:
        set_status("analyzing")
        job.stage = "chapter_detection"

        chapters = detect_chapters(pdf_path)
        doc = fitz.open(str(pdf_path))
        total_pages = doc.page_count
        job.total_pages = total_pages

        init_manifest(analysis_dir, book_uuid, total_pages)

        # Determine LLM providers (options may override config)
        if not cfg.llms.analysis_model and not opts.analysis_model:
            raise RuntimeError(
                "No VLM configured for deep analysis. Add 'analysis_model' under 'llms' in "
                "config.json pointing to a vision-capable model (e.g. Qwen3.5-VL). "
                "Deep analysis requires a VLM for scanned page OCR and figure detection — "
                "refusing to fall back to a text-only model."
            )
        analysis_model_cfg = cfg.llms.analysis_model
        analysis_provider = (
            _build_provider(opts.analysis_model, analysis_model_cfg)
            if opts.analysis_model else get_provider(analysis_model_cfg)
        )
        extraction_provider = (
            _build_provider(opts.extraction_model, cfg.llms.extraction_model)
            if opts.extraction_model else get_provider(cfg.llms.extraction_model)
        )

        # Build OCR prompt (once, reused per scanned page)
        _lang_instr = (
            f"\nTranslate all extracted text to {opts.language}."
            if opts.language else ""
        )
        _extra_instr = (
            f"\nAdditional instructions: {opts.extra_prompt}"
            if opts.extra_prompt else ""
        )
        ocr_prompt = (
            "CRITICAL: ALL mathematical expressions — including single variables with "
            "subscripts/superscripts — MUST be wrapped in LaTeX delimiters. "
            "Inline math: $formula$  (e.g. $A_H$, $\\frac{\\partial f}{\\partial t}$). "
            "Display math on its own line: $$formula$$  (e.g. $$E = mc^2$$). "
            "Never write raw LaTeX commands (\\frac, \\alpha, \\left, etc.) outside $ delimiters.\n"
            "Extract all text from this page verbatim. "
            "Output plain text + LaTeX only — no HTML tags, no markdown code fences.\n"
            "STRUCTURE RULES:\n"
            "- Chapter/section headings (visually larger, bold, or numbered like '1.2 Title' / '第N章'): "
            "prefix with ## (top-level section) or ### (subsection), e.g. '## 1.2 量子光學'.\n"
            "- Tables: use markdown pipe format with a separator row, e.g. '| A | B |\\n| --- | --- |\\n| x | y |'.\n"
            "- Blank line before and after each heading and table.\n"
            "- Table-of-contents pages: extract text as-is (no special markup needed)."
            + _lang_instr + _extra_instr
        )

        img_counter = [0]
        all_images: list[ImageRecord] = []
        ch_texts: dict[int, str] = {}  # chapter index → accumulated text
        summarized_chapters: set[int] = set()
        toc_all_entries: list[tuple[str, str]] = []  # entries from all TOC pages combined
        toc_ch_idx: int | None = None               # chapter that owns the TOC
        toc_first_page: int | None = None            # first detected TOC page number

        # VLM loop guard: a single page producing more than this is a repetition loop
        _OCR_MAX_CHARS = 8000

        OCR_MIN = getattr(cfg.ocr, "min_chars_threshold", 50)
        page_start = max(0, opts.page_start) if opts.page_start is not None else 0
        page_end   = min(total_pages, opts.page_end) if opts.page_end is not None else total_pages

        # Build a lookup: last page (inclusive, 0-based) → chapter index
        ch_last_page: dict[int, int] = {ch.end_page - 1: ch.index for ch in chapters}

        # ── Per-page loop ──────────────────────────────────────────────────
        for page_num in range(page_start, page_end):
            if job.cancelled:
                set_status("failed")
                doc.close()
                return

            job.current_page = page_num + 1
            job.stage = f"page_{page_num + 1}"
            page = doc[page_num]

            # Determine if page is native or scanned
            raw_text = page.get_text()
            is_scanned = len(raw_text.strip()) < OCR_MIN

            is_toc_page = False

            if is_scanned:
                # Render page as image for VLM
                mat = fitz.Matrix(2.0, 2.0)  # 2× scale for quality
                pix = page.get_pixmap(matrix=mat)
                from PIL import Image as PILImage
                import io
                img_bytes = pix.tobytes("png")
                page_img = PILImage.open(io.BytesIO(img_bytes))
                page_w, page_h = page_img.size

                # OCR text — failure is fatal: continuing with empty text produces hallucinated output
                from backend.analysis.image_extractor import _pil_to_b64, _call_vlm
                b64 = _pil_to_b64(page_img)
                try:
                    ocr_text = _call_vlm(analysis_provider, ocr_prompt, b64)
                except Exception as e:
                    raise RuntimeError(
                        f"VLM OCR failed on page {page_num + 1} of '{pdf_path.name}': {e}. "
                        "Fix 'analysis_model' in config.json or ensure the VLM server is running."
                    ) from e

                # Guard against VLM repetition loops producing runaway output
                if len(ocr_text) > _OCR_MAX_CHARS:
                    log.warning("Page %d OCR output truncated (%d chars → %d): likely VLM loop",
                                page_num, len(ocr_text), _OCR_MAX_CHARS)
                    ocr_text = ocr_text[:_OCR_MAX_CHARS]

                # TOC detection: accumulate entries across all TOC pages; skip figure extraction.
                toc_entries = extract_toc_entries(ocr_text)
                if toc_entries:
                    log.info("TOC page detected on page %d (%d entries)", page_num, len(toc_entries))
                    toc_all_entries.extend(toc_entries)
                    if toc_ch_idx is None:
                        toc_ch_idx = _page_to_chapter(page_num, chapters)
                    if toc_first_page is None:
                        toc_first_page = page_num
                    page_images = []
                    is_toc_page = True
                elif _is_toc_hdr(ocr_text):
                    # TOC header detected but entries unreadable (e.g. VLM dot-loop).
                    # Suppress image extraction and claim the position without entries.
                    log.info("TOC header page detected on page %d (no parseable entries)", page_num)
                    if toc_ch_idx is None:
                        toc_ch_idx = _page_to_chapter(page_num, chapters)
                    if toc_first_page is None:
                        toc_first_page = page_num
                    page_images = []
                    is_toc_page = True
                elif opts.mode != "quick":
                    # Figure detection + description in one VLM call
                    page_images = extract_scanned_images(
                        page_img, page_num, images_dir, img_counter,
                        analysis_provider, page_w, page_h
                    )
                else:
                    page_images = []
            else:
                ocr_text = raw_text
                page_images = (
                    extract_native_images(page, images_dir, img_counter)
                    if opts.mode != "quick" else []
                )

            # Assign page text to chapter (TOC pages are held back for combined table)
            if not is_toc_page:
                ch_idx = _page_to_chapter(page_num, chapters)
                if ch_idx is not None:
                    cleaned = _normalize_ocr_text(ocr_text or "")
                    ch_texts[ch_idx] = ch_texts.get(ch_idx, "") + f"[[PAGE:{page_num}]]\n" + cleaned + "\n"
            elif toc_first_page == page_num:
                # Insert a placeholder at this exact position so the TOC table lands
                # in page order (not appended at the end of the chapter).
                ch_idx = toc_ch_idx
                if ch_idx is not None:
                    ch_texts[ch_idx] = ch_texts.get(ch_idx, "") + f"[[PAGE:{page_num}]]\n\x00TOC\x00\n"

            # Describe native images (scanned images already have descriptions from bbox+desc call)
            for img_rec in page_images:
                if not img_rec.description:
                    img_path = images_dir / img_rec.filename
                    describe_image(img_path, analysis_provider, img_rec)
                img_rec.model_used = analysis_model_cfg.model_name
                all_images.append(img_rec)

            job.record_page()
            update_manifest_page(analysis_dir, page_num + 1, {})

            # Summarize chapter immediately when its last page is done
            if page_num in ch_last_page and not job.cancelled:
                finished_ch_idx = ch_last_page[page_num]
                ch_obj = next((c for c in chapters if c.index == finished_ch_idx), None)
                ch_acc = ch_texts.get(finished_ch_idx, "")
                # Skip TOC chapter here — its entries are combined after doc.close()
                if finished_ch_idx != toc_ch_idx and ch_obj and ch_acc.strip():
                    job.stage = f"summarizing_ch_{finished_ch_idx}"
                    ch_acc = _join_cross_page_paragraphs(ch_acc)
                    ch_texts[finished_ch_idx] = ch_acc
                    summary = summarize_chapter(
                        ch_acc, extraction_provider, ch_obj.title,
                        language=opts.language, extra_prompt=opts.extra_prompt,
                    )
                    (text_dir / f"ch_{finished_ch_idx:02d}_summary.txt").write_text(
                        summary, encoding="utf-8"
                    )
                    summarized_chapters.add(finished_ch_idx)
                job.stage = f"page_{page_num + 1}"

        doc.close()

        # ── Combine all TOC pages into one table ───────────────────────────
        if toc_ch_idx is not None:
            ch = ch_texts.get(toc_ch_idx, "")
            if toc_all_entries:
                combined = entries_to_markdown_table(toc_all_entries)
                if "\x00TOC\x00" in ch:
                    ch_texts[toc_ch_idx] = ch.replace("\x00TOC\x00", combined)
                else:
                    ch_texts[toc_ch_idx] = ch + combined + "\n"
                log.info("TOC: combined %d entries into chapter %d", len(toc_all_entries), toc_ch_idx)
            else:
                # Header-only detection — no parseable entries; remove placeholder
                ch_texts[toc_ch_idx] = ch.replace("\x00TOC\x00", "")

            # Remove images from the TOC chapter — superseded by the text table.
            toc_ch_obj = next((c for c in chapters if c.index == toc_ch_idx), None)
            if toc_ch_obj:
                before = len(all_images)
                all_images = [img for img in all_images
                              if not (toc_ch_obj.start_page <= img.page < toc_ch_obj.end_page)]
                removed = before - len(all_images)
                if removed:
                    log.info("TOC: removed %d images from TOC chapter pages", removed)

        # ── Join cross-page paragraphs (for chapters not yet joined in-loop) ──
        for ch in chapters:
            if ch.index not in summarized_chapters and ch.index in ch_texts:
                ch_texts[ch.index] = _join_cross_page_paragraphs(ch_texts[ch.index])

        # ── Write chapter text files ───────────────────────────────────────
        job.stage = "writing_text"
        for ch in chapters:
            ch_file = text_dir / f"ch_{ch.index:02d}.txt"
            ch_file.write_text(ch_texts.get(ch.index, ""), encoding="utf-8")

        # ── Summarize any chapters not yet covered (e.g. truncated page range) ──
        for ch in chapters:
            if ch.index in summarized_chapters or job.cancelled:
                continue
            ch_text = ch_texts.get(ch.index, "")
            if not ch_text.strip():
                continue
            summary = summarize_chapter(ch_text, extraction_provider, ch.title,
                                        language=opts.language, extra_prompt=opts.extra_prompt)
            (text_dir / f"ch_{ch.index:02d}_summary.txt").write_text(summary, encoding="utf-8")

        # ── Image JSON sidecars ───────────────────────────────────────────
        import json
        for img in all_images:
            sidecar = images_dir / img.filename.replace(".png", ".json")
            sidecar.write_text(json.dumps({
                "page": img.page,
                "bbox": img.bbox,
                "description": img.description,
                "model_used": img.model_used,
                "tokens_used": img.tokens_used,
            }, ensure_ascii=False), encoding="utf-8")

        # ── HTML view ─────────────────────────────────────────────────────
        job.stage = "building_html"
        book_title = _get_book_title(book_uuid)
        html_content = build_view_html(book_title, chapters, all_images, text_dir)
        (analysis_dir / "view.html").write_text(html_content, encoding="utf-8")

        # ── Per-chapter site ───────────────────────────────────────────────
        chapters_dir = analysis_dir / "chapters"
        chapters_dir.mkdir(exist_ok=True)
        chapter_files = build_chapter_site(book_title, chapters, all_images, text_dir)
        for filename, ch_html in chapter_files.items():
            (chapters_dir / filename).write_text(ch_html, encoding="utf-8")

        # ── Final manifest ────────────────────────────────────────────────
        finalize_manifest(
            analysis_dir,
            status="done",
            chapters=[{"index": c.index, "title": c.title,
                       "start_page": c.start_page, "end_page": c.end_page} for c in chapters],
            images=[{"filename": i.filename, "page": i.page, "bbox": i.bbox} for i in all_images],
        )

        set_status("done")
        log.info("Analysis complete for %s (%d pages, %d images)", book_uuid, total_pages, len(all_images))

    except Exception as e:
        log.exception("Analysis failed for %s: %s", book_uuid, e)
        job.error = str(e)
        try:
            from backend.analysis.manifest import finalize_manifest
            finalize_manifest(analysis_dir, status="failed", chapters=[], images=[], error=str(e))
        except Exception:
            pass
        set_status("failed")


def _update_book_status(book_uuid: str, status: str) -> None:
    try:
        from backend.db.core import get_core_session
        from backend.models.book import Book
        from sqlmodel import select
        from datetime import datetime
        with get_core_session() as session:
            book = session.exec(select(Book).where(Book.id == book_uuid)).first()
            if book:
                book.analysis_status = status
                book.updated_at = datetime.utcnow()
                session.commit()
    except Exception as e:
        log.warning("Failed to update book status for %s: %s", book_uuid, e)


def _page_to_chapter(page_num: int, chapters) -> int | None:
    for ch in chapters:
        if ch.start_page <= page_num < ch.end_page:
            return ch.index
    return None


def _get_book_title(book_uuid: str) -> str:
    try:
        from backend.db.core import get_core_session
        from backend.models.book import Book
        from sqlmodel import select
        with get_core_session() as session:
            book = session.exec(select(Book).where(Book.id == book_uuid)).first()
            return book.title if book else book_uuid
    except Exception:
        return book_uuid


def recover_stale_jobs(cfg) -> None:
    """On startup: mark any books stuck in 'analyzing' as 'failed'."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.analysis.manifest import read_manifest
    from sqlmodel import select
    from datetime import datetime

    try:
        with get_core_session() as session:
            stale = session.exec(
                select(Book).where(Book.analysis_status == "analyzing")
            ).all()
            for book in stale:
                manifest = read_manifest(cfg.analysis_dir / book.id)
                # If manifest says done it somehow wasn't written; if analyzing mark failed
                if manifest.get("status") != "done":
                    book.analysis_status = "failed"
                    book.updated_at = datetime.utcnow()
                    log.warning("Recovered stale analysis job for %s", book.id)
            session.commit()
    except Exception as e:
        log.warning("Startup recovery failed: %s", e)
