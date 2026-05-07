"""Read/write helpers for analysis/manifest.json."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_manifest(analysis_dir: Path) -> dict:
    path = analysis_dir / "manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(analysis_dir: Path, data: dict) -> None:
    path = analysis_dir / "manifest.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def update_manifest_page(analysis_dir: Path, current_page: int, token_delta: dict[str, int]) -> None:
    """Incremental update after each page — safe to call frequently."""
    data = read_manifest(analysis_dir)
    data["current_page"] = current_page

    usage = data.get("token_usage", {})
    for key, val in token_delta.items():
        usage[key] = usage.get(key, 0) + val
    data["token_usage"] = usage

    write_manifest(analysis_dir, data)


def init_manifest(
    analysis_dir: Path,
    book_uuid: str,
    total_pages: int,
    analysis_version: str = "1",
) -> dict:
    data: dict[str, Any] = {
        "book_uuid": book_uuid,
        "analysis_version": analysis_version,
        "status": "analyzing",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "total_pages": total_pages,
        "current_page": 0,
        "chapters": [],
        "images": [],
        "token_usage": {},
    }
    write_manifest(analysis_dir, data)
    return data


def finalize_manifest(
    analysis_dir: Path,
    status: str,
    chapters: list[dict],
    images: list[dict],
    error: str | None = None,
) -> None:
    data = read_manifest(analysis_dir)
    data["status"] = status
    data["completed_at"] = datetime.now(timezone.utc).isoformat()
    data["chapters"] = chapters
    data["images"] = images
    if error:
        data["error"] = error
    write_manifest(analysis_dir, data)
