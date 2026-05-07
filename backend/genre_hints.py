import json
from pathlib import Path

_FILENAME = "genre_hints.json"


def load_hints(base_dir: Path) -> dict[str, str]:
    path = base_dir / _FILENAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_hints(base_dir: Path, hints: dict[str, str]) -> None:
    path = base_dir / _FILENAME
    path.write_text(json.dumps(hints, ensure_ascii=False, indent=2), encoding="utf-8")


def patch_hints(base_dir: Path, updates: dict[str, str]) -> dict[str, str]:
    hints = load_hints(base_dir)
    for k, v in updates.items():
        if v:
            hints[k] = v
        else:
            hints.pop(k, None)
    save_hints(base_dir, hints)
    return hints
