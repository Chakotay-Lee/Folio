import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".epub", ".txt", ".md"}

_task: asyncio.Task | None = None
_in_progress: set[str] = set()   # paths currently being ingested


async def _watch_loop(paths: list[Path], config) -> None:
    from watchfiles import awatch, Change

    str_paths = [str(p) for p in paths if p.exists()]
    if not str_paths:
        logger.warning("No watch folders exist yet — skipping file watcher")
        return

    logger.info("Watching folders: %s", str_paths)
    async for changes in awatch(*str_paths):
        for change_type, path_str in changes:
            if change_type not in (Change.added, Change.modified):
                continue
            path = Path(path_str)
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if path_str in _in_progress:
                logger.debug("Skipping already-in-progress file: %s", path.name)
                continue
            logger.info("Detected new file: %s", path)
            _in_progress.add(path_str)
            try:
                await asyncio.to_thread(_ingest, path, config)
            finally:
                _in_progress.discard(path_str)


def _ingest(path: Path, config) -> None:
    from backend.ingestion.pipeline import ingest_file
    from backend.ingestion.log_store import append_log, IngestionLog
    try:
        result = ingest_file(path, config)
        logger.info("Auto-ingested %s: %s", path.name, result.status)
    except Exception as e:
        logger.error("Auto-ingest failed for %s: %s", path.name, e)
        append_log(IngestionLog(uuid="", title=path.name, status="error", message=str(e)))


def start_watcher(paths: list[Path], config) -> None:
    global _task
    _task = asyncio.create_task(_watch_loop(paths, config))


def stop_watcher() -> None:
    global _task
    if _task:
        _task.cancel()
        _task = None


def scan_all(paths: list[Path], config) -> list[dict]:
    """Synchronously scan all folders and ingest any untracked files."""
    from backend.ingestion.pipeline import ingest_file
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select

    with get_core_session() as session:
        known_paths = set(session.exec(select(Book.relative_path)).all())

    books_root = config.storage.books_root

    results = []
    for folder in paths:
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if ".folio" in path.parts:
                continue
            try:
                rel = str(path.relative_to(books_root))
            except ValueError:
                rel = str(path)
            if rel in known_paths:
                continue
            try:
                result = ingest_file(path, config)
                results.append({"file": path.name, "status": result.status, "message": result.message})
            except Exception as e:
                results.append({"file": path.name, "status": "error", "message": str(e)})

    return results
