"""Figure extraction for native and scanned PDF pages."""
from __future__ import annotations
import base64
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)
MIN_DIM = 50  # pixels


@dataclass
class ImageRecord:
    filename: str       # img_001.png
    page: int           # 0-based page number
    bbox: list[int]     # [x1, y1, x2, y2] in page coords
    description: str = ""
    model_used: str = ""
    tokens_used: int = 0


def extract_native_images(
    page,               # fitz.Page
    images_dir: Path,
    img_counter: list[int],  # [n] mutable counter shared across pages
) -> list[ImageRecord]:
    """Extract embedded images ≥ MIN_DIM×MIN_DIM from a native PDF page."""
    records: list[ImageRecord] = []
    doc = page.parent

    for img_info in page.get_images(full=True):
        xref = img_info[0]
        try:
            base_img = doc.extract_image(xref)
        except Exception as e:
            log.debug("Failed to extract image xref=%d: %s", xref, e)
            continue

        w, h = base_img.get("width", 0), base_img.get("height", 0)
        if w < MIN_DIM or h < MIN_DIM:
            continue

        img_data = base_img["image"]
        img_counter[0] += 1
        n = img_counter[0]
        filename = f"img_{n:03d}.png"
        out_path = images_dir / filename

        # Convert to PNG via PIL if not already PNG
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(img_data))
            img.save(str(out_path), format="PNG")
        except Exception:
            out_path.write_bytes(img_data)

        records.append(ImageRecord(
            filename=filename,
            page=page.number,
            bbox=[0, 0, w, h],
        ))

    return records


MIN_FIGURE_DIM = 80  # pixels — skip tiny detections that are likely text/labels

def extract_scanned_images(
    page_img,           # PIL.Image of the rendered page
    page_number: int,
    images_dir: Path,
    img_counter: list[int],
    llm_provider,       # LLMProvider instance with chat capability
    page_w: int,
    page_h: int,
) -> list[ImageRecord]:
    """Use VLM to detect figure bounding boxes and descriptions in one call, then crop."""
    from PIL import Image

    prompt = (
        f"The image is {page_w}×{page_h} pixels. "
        "List all figures, diagrams, charts, or photographs visible in this page — NOT text paragraphs or captions. "
        "For each figure return a JSON object with three fields: "
        '"bbox_2d" ([x1, y1, x2, y2] integer pixel coordinates), '
        '"label" (a short title), and '
        '"description" (1–3 sentences describing the figure for a reader\'s reference). '
        "Return a JSON array of these objects. "
        f"All coordinates must be integers in range 0–{page_w} (x) and 0–{page_h} (y). "
        "If there are no figures, return []."
    )

    img_b64 = _pil_to_b64(page_img)
    raw_text = _call_vlm(llm_provider, prompt, img_b64)
    log.debug("VLM bbox raw response (page %d): %s", page_number, raw_text[:600])

    detections = _parse_bbox_response(raw_text, page_w, page_h)
    log.debug("Parsed detections (page %d, image %dx%d): %s", page_number, page_w, page_h,
              [(d["bbox"], d["description"][:40]) for d in detections])
    records: list[ImageRecord] = []

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        if (x2 - x1) < MIN_FIGURE_DIM or (y2 - y1) < MIN_FIGURE_DIM:
            log.debug("Skipping tiny box %s on page %d", det["bbox"], page_number)
            continue
        try:
            cropped = page_img.crop((x1, y1, x2, y2))
        except Exception as e:
            log.warning("Crop failed for box %s on page %d: %s", det["bbox"], page_number, e)
            continue

        img_counter[0] += 1
        n = img_counter[0]
        filename = f"img_{n:03d}.png"
        cropped.save(str(images_dir / filename), format="PNG")

        records.append(ImageRecord(
            filename=filename,
            page=page_number,
            bbox=list(det["bbox"]),
            description=det["description"],
        ))

    return records


def describe_image(
    image_path: Path,
    llm_provider,
    record: ImageRecord,
) -> ImageRecord:
    """Call VLM to generate a textual description for a figure."""
    from PIL import Image
    try:
        img = Image.open(str(image_path))
        img_b64 = _pil_to_b64(img)
        desc = _call_vlm(
            llm_provider,
            "Describe this figure concisely in 1-3 sentences for a reader's reference.",
            img_b64,
        )
        record.description = desc.strip()
    except Exception as e:
        log.warning("VLM description failed for %s: %s", image_path.name, e)
        record.description = ""
    return record


# ── helpers ───────────────────────────────────────────────────────────────────

def _pil_to_b64(img) -> str:
    from PIL import Image
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _call_vlm(provider, prompt: str, img_b64: str) -> str:
    """Call an OpenAI-compatible provider with an image + text prompt."""
    import httpx

    url = provider.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": provider.model_name,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
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


def _parse_bbox_response(
    text: str, page_w: int, page_h: int
) -> list[dict]:
    """Parse VLM response into a list of {"bbox": (x1,y1,x2,y2), "description": str} dicts.

    Handles:
    - Pixel coordinates (direct use)
    - 0–1000 normalized (Qwen2-VL style): auto-detected and scaled when image >1000px
    - 0.0–1.0 float normalized (LLaVA style): auto-detected and scaled
    - Markdown ```json ... ``` wrappers
    """
    # Find JSON array in response
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    try:
        items = json.loads(text[start:end])
    except json.JSONDecodeError:
        return []

    # Collect raw float values and descriptions before converting to int
    raw: list[tuple[float, float, float, float, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_box = item.get("bbox_2d") or item.get("bbox") or item.get("bounding_box")
        if not raw_box or len(raw_box) != 4:
            continue
        try:
            fx1, fy1, fx2, fy2 = (float(v) for v in raw_box)
        except (TypeError, ValueError):
            continue
        if fx1 >= fx2 or fy1 >= fy2:
            continue
        desc = str(item.get("description") or item.get("label") or "").strip()
        raw.append((fx1, fy1, fx2, fy2, desc))

    if not raw:
        return []

    # Detect coordinate space from max value across all boxes
    max_coord = max(max(fx2, fy2) for fx1, fy1, fx2, fy2, _ in raw)

    if max_coord <= 1.0:
        # 0.0–1.0 float normalized (LLaVA / relative coords)
        scale_x, scale_y = page_w, page_h
    elif max_coord <= 1000 and page_w > 1000 and page_h > 1000:
        # 0–1000 normalized (Qwen2-VL style): both dims must exceed 1000 to avoid
        # false positives on images that are just slightly taller than 1000px.
        scale_x, scale_y = page_w / 1000, page_h / 1000
        log.debug("Detected 0-1000 normalized coords, scaling to %dx%d", page_w, page_h)
    else:
        # Already pixel coordinates
        scale_x, scale_y = 1.0, 1.0

    results: list[dict] = []
    for fx1, fy1, fx2, fy2, desc in raw:
        x1 = max(0, min(int(round(fx1 * scale_x)), page_w))
        y1 = max(0, min(int(round(fy1 * scale_y)), page_h))
        x2 = max(0, min(int(round(fx2 * scale_x)), page_w))
        y2 = max(0, min(int(round(fy2 * scale_y)), page_h))

        if x1 >= x2 or y1 >= y2:
            log.debug("Degenerate bbox after scaling/clamping, discarded")
            continue

        results.append({"bbox": (x1, y1, x2, y2), "description": desc})

    return results
