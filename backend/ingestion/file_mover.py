import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_ILLEGAL = r'/:\x00<>|?*"\\'


def sanitize_path_segment(s: str) -> str:
    for ch in _ILLEGAL:
        s = s.replace(ch, '_')
    return s.strip().strip('.')


def genre_to_dir(genre_path: str | None) -> Path:
    if not genre_path or not genre_path.strip():
        return Path('未分類')
    parts = [p.strip() for p in genre_path.split(' > ') if p.strip()][:3]
    sanitized = [sanitize_path_segment(p) for p in parts if sanitize_path_segment(p)]
    return Path(*sanitized) if sanitized else Path('未分類')


def _unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    i = 2
    while True:
        candidate = dest.parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _cleanup_empty_dirs(start: Path, stop: Path) -> None:
    p = start
    while p != stop and p != p.parent:
        try:
            p.rmdir()
            p = p.parent
        except OSError:
            break


def move_to_library(
    src: Path,
    genre_path: str | None,
    books_root: Path,
) -> str | None:
    """Move src file into books_root/<genre_dir>/ and return new relative path.

    Returns None if move fails (caller should keep original path).
    """
    if not src.exists():
        logger.warning("File not found for move: %s", src)
        return None

    genre_dir = genre_to_dir(genre_path)
    dest_dir = books_root / genre_dir
    dest = _unique_dest(dest_dir / src.name)

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        return str(dest.relative_to(books_root))
    except Exception as e:
        logger.warning("File move failed (%s → %s): %s", src, dest, e)
        return None
