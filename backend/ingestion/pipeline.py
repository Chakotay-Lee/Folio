import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    uuid: str
    title: str
    status: str
    message: str


def _to_str(v, default=""):
    if isinstance(v, list):
        return " > ".join(str(x) for x in v)
    return v or default


def ingest_file(file_path: str | Path, config) -> IngestionResult:
    from backend.ingestion.extractor import extract_text, SUPPORTED_FORMATS
    from backend.ingestion.dedup import compute_simhash, is_duplicate, get_all_simhashes
    from backend.ingestion.log_store import append_log, IngestionLog
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend import vector_store as vs
    import uuid as _uuid
    from datetime import datetime

    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_FORMATS:
        result = IngestionResult(uuid="", title=path.name, status="error", message=f"Unsupported format: {ext}")
        append_log(IngestionLog(**result.__dict__))
        return result

    text = extract_text(path, max_pages=config.search.max_pages_to_analyze)

    with get_core_session() as session:
        existing_hashes = get_all_simhashes(session)
        hash_val = compute_simhash(text)

        if is_duplicate(text, existing_hashes):
            result = IngestionResult(uuid="", title=path.name, status="duplicate", message="SimHash similarity > 95%")
            append_log(IngestionLog(**result.__dict__))
            return result

        from backend.llm.factory import get_provider
        from backend.models.book import Book as _BookModel
        existing_genres = list(session.exec(
            __import__("sqlmodel").select(_BookModel.genre_path).where(_BookModel.genre_path != None)
        ).all())
        provider = get_provider(config.llms.extraction_model)
        language = getattr(config, 'content_language', 'en')
        try:
            metadata = provider.extract_metadata(text, existing_genres=existing_genres, language=language)
        except Exception as e:
            logger.warning("LLM metadata extraction failed: %s — using filename fallback", e)
            metadata = {"title": path.stem, "author": None, "summary": "", "tags": [], "genre_path": ""}

        import json
        book_uuid = str(_uuid.uuid4())
        books_root = config.storage.books_root
        try:
            relative_path = str(path.relative_to(books_root))
        except ValueError:
            relative_path = str(path)

        from sqlmodel import select as _select
        existing = session.exec(_select(Book).where(Book.relative_path == relative_path)).first()
        if existing:
            result = IngestionResult(uuid=existing.id, title=existing.title, status="duplicate", message="Already indexed")
            append_log(IngestionLog(**result.__dict__))
            return result

        tags_raw = metadata.get("tags", [])
        if isinstance(tags_raw, str):
            import ast
            try:
                tags_raw = ast.literal_eval(tags_raw)
            except Exception:
                tags_raw = [tags_raw]

        book = Book(
            id=book_uuid,
            relative_path=relative_path,
            title=_to_str(metadata.get("title")) or path.stem,
            author=_to_str(metadata.get("author")) or None,
            genre_path=_to_str(metadata.get("genre_path")),
            summary=_to_str(metadata.get("summary")),
            tags_json=json.dumps(list(dict.fromkeys(tags_raw)) if isinstance(tags_raw, list) else [], ensure_ascii=False),
            file_format=ext.lstrip("."),
            file_size_bytes=path.stat().st_size,
            simhash=hash_val,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(book)
        session.commit()
        book_title = book.title
        book_author = book.author or ""
        book_genre = book.genre_path or ""
        book_format = book.file_format

    # Extract cover at index time — stored as assets/covers/{uuid}.jpg
    from backend.ingestion.cover import extract_cover
    extract_cover(path, book_uuid, config.storage.assets)

    # Move source file into Books/<genre>/ and update DB relative_path
    from backend.ingestion.file_mover import move_to_library
    new_rel = move_to_library(path, book_genre, config.storage.books_root)
    if new_rel and new_rel != relative_path:
        with get_core_session() as session:
            from sqlmodel import select as _sel
            from backend.models.book import Book as _Book
            book_rec = session.exec(_sel(_Book).where(_Book.id == book_uuid)).first()
            if book_rec:
                book_rec.relative_path = new_rel
                session.commit()

    vs.upsert_document(
        uuid=book_uuid,
        summary=_to_str(metadata.get("summary")),
        tags=tags_raw if isinstance(tags_raw, list) else [],
        metadata={
            "title": book_title,
            "author": book_author,
            "genre_path": book_genre,
            "file_format": book_format,
        },
    )

    result = IngestionResult(uuid=book_uuid, title=book_title, status="success", message="")
    append_log(IngestionLog(**result.__dict__))
    return result
