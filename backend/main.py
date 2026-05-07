import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config_loader import load_config, AppConfig
from backend.db.core import init_core_db
from backend.db.activity import init_activity_db, reset_activity_db
from backend.fingerprint import validate_fingerprint
from backend import vector_store as vs
from backend import watcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = os.path.abspath(os.environ.get("FOLIO_CONFIG", "./config.json"))
    cfg: AppConfig = load_config(config_path)
    app.state.config = cfg
    app.state.config_path = config_path

    init_core_db(cfg.storage.library_core_db)
    init_activity_db(cfg.storage.user_activity_db)

    emb = cfg.llms.embedding_model
    vs.init_vector_store(
        store_path=cfg.storage.vector_store,
        embedding_model=emb.model_name,
        api_key=emb.api_key,
        base_url=emb.base_url,
        dimension=emb.dimension,
    )
    app.state.vector_store = vs

    fp_path = cfg.base_dir / ".library_fingerprint.json"
    is_fresh = validate_fingerprint(fp_path, emb.model_name, emb.dimension)
    app.state.index_stale = not is_fresh

    from backend.ingestion.ocr import init_ocr
    init_ocr(cfg)

    from backend.analysis.pipeline import recover_stale_jobs
    recover_stale_jobs(cfg)

    watcher.start_watcher(cfg.storage.watch_folders, cfg)

    yield

    watcher.stop_watcher()


app = FastAPI(title="Folio API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependencies ──────────────────────────────────────────────────────────────

def require_fresh_index(request: Request):
    if request.app.state.index_stale:
        raise HTTPException(
            status_code=409,
            detail={"error": "index_stale", "message": "Embedding model changed. Re-index required before searching."},
        )


# ── Routers ───────────────────────────────────────────────────────────────────

from fastapi import APIRouter

health_router = APIRouter()
search_router = APIRouter(prefix="/api/search", dependencies=[Depends(require_fresh_index)])
books_router = APIRouter(prefix="/api/books")
config_router = APIRouter(prefix="/api/config")
user_data_router = APIRouter(prefix="/api/user-data")
reindex_router = APIRouter(prefix="/api/reindex")
ingestion_router = APIRouter(prefix="/api/ingestion")
folders_router = APIRouter(prefix="/api/folders")


@health_router.get("/api/health")
def health():
    return {"status": "ok"}


@search_router.get("/semantic")
def search_semantic(q: str, request: Request):
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select
    results = request.app.state.vector_store.search(q, top_k=request.app.state.config.search.top_k)
    if not results:
        return {"query": q, "results": []}
    uuids = [uid for uid, _ in results]
    scores = {uid: score for uid, score in results}
    with get_core_session() as session:
        books = session.exec(select(Book).where(Book.id.in_(uuids))).all()
    book_map = {b.id: b.model_dump() for b in books}
    joined = [
        {**book_map[uid], "score": scores[uid]}
        for uid in uuids if uid in book_map
    ]
    return {"query": q, "results": joined}


@books_router.get("")
def list_books(page: int = 1, limit: int = 24, genre: str | None = None,
               tag: str | None = None, q: str | None = None):
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select, func
    from sqlalchemy import or_

    with get_core_session() as session:
        filters = []
        if genre:
            filters.append(or_(Book.genre_path == genre, Book.genre_path.like(genre + " > %")))
        if tag:
            filters.append(Book.tags_json.like(f'%"{tag}"%'))
        if q:
            ql = f"%{q}%"
            filters.append(or_(
                Book.title.ilike(ql),
                Book.author.ilike(ql),
                Book.summary.ilike(ql),
            ))

        stmt = select(Book)
        count_stmt = select(func.count()).select_from(Book)
        for f in filters:
            stmt = stmt.where(f)
            count_stmt = count_stmt.where(f)

        total = session.exec(count_stmt).one()
        books = session.exec(stmt.offset((page - 1) * limit).limit(limit)).all()

    return {
        "items": [b.model_dump() for b in books],
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
    }


@books_router.get("/stats")
def book_stats():
    import json as _json
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select, func

    with get_core_session() as session:
        total_books = session.exec(select(func.count()).select_from(Book)).one()
        total_bytes = session.exec(select(func.sum(Book.file_size_bytes))).one() or 0
        genre_rows = session.exec(select(Book.genre_path).where(Book.genre_path.isnot(None))).all()
        top_genres = {g.split(" > ")[0] for g in genre_rows if g}
        format_rows = session.exec(
            select(Book.file_format, func.count().label("cnt")).group_by(Book.file_format)
        ).all()
        tag_rows = session.exec(select(Book.tags_json).where(Book.tags_json.isnot(None))).all()
        all_tags: set = set()
        for row in tag_rows:
            try:
                all_tags.update(_json.loads(row))
            except Exception:
                continue

    return {
        "total_books": total_books,
        "total_bytes": int(total_bytes),
        "genre_count": len(top_genres),
        "tag_count": len(all_tags),
        "formats": {r[0]: r[1] for r in format_rows},
    }


@books_router.get("/tags")
def book_tags():
    import json as _json
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select

    with get_core_session() as session:
        rows = session.exec(select(Book.tags_json).where(Book.tags_json.isnot(None))).all()

    counts: dict = {}
    for row in rows:
        try:
            for tag in _json.loads(row):
                counts[tag] = counts.get(tag, 0) + 1
        except Exception:
            continue

    return sorted([{"tag": t, "count": c} for t, c in counts.items()], key=lambda x: -x["count"])


@books_router.get("/genres")
def book_genres():
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select, func

    with get_core_session() as session:
        rows = session.exec(
            select(Book.genre_path, func.count().label("cnt"))
            .where(Book.genre_path.isnot(None))
            .group_by(Book.genre_path)
        ).all()

    return [{"genre_path": r[0], "count": r[1]} for r in rows]


@books_router.get("/genres/hints")
def get_genre_hints(request: Request):
    from backend.genre_hints import load_hints
    cfg: AppConfig = request.app.state.config
    return load_hints(cfg.base_dir)


@books_router.put("/genres/hints")
async def put_genre_hints(request: Request):
    from backend.genre_hints import patch_hints
    cfg: AppConfig = request.app.state.config
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Body must be a JSON object {genre_path: description}")
    return patch_hints(cfg.base_dir, body)


@books_router.post("/genres/expand/names")
async def expand_genre_names(request: Request):
    """Phase 1: fetch books under genre and ask LLM to suggest sub-genre names."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.llm.factory import get_provider
    from backend.llm.prompts import build_genre_names_prompt
    from backend.genre_hints import load_hints
    from sqlmodel import select, or_
    import json as _json
    import asyncio

    body = await request.json()
    genre_prefix = body.get("genre_prefix", "").strip()
    if not genre_prefix:
        raise HTTPException(status_code=422, detail="genre_prefix is required")

    cfg: AppConfig = request.app.state.config

    with get_core_session() as session:
        rows = session.exec(
            select(Book).where(
                or_(Book.genre_path == genre_prefix,
                    Book.genre_path.like(genre_prefix + " > %"))
            )
        ).all()

    if not rows:
        raise HTTPException(status_code=404, detail="No books found under this genre")

    books_data = []
    for b in rows:
        try:
            tags = _json.loads(b.tags_json) if b.tags_json else []
        except Exception:
            tags = []
        books_data.append({"id": b.id, "title": b.title, "tags": tags})

    provider = get_provider(cfg.llms.extraction_model)
    names_prompt = build_genre_names_prompt(genre_prefix, books_data, language=cfg.content_language)

    loop = asyncio.get_event_loop()
    names_raw = await loop.run_in_executor(None, lambda: provider.complete(names_prompt, max_tokens=1024))

    raw = (names_raw or "").strip()
    start = raw.find("{"); end = raw.rfind("}") + 1
    if start == -1 or end <= start:
        raise HTTPException(status_code=500, detail=f"LLM returned no valid JSON: {raw[:150]!r}")

    sub_genres = _json.loads(raw[start:end]).get("sub_genres", [])
    if not sub_genres:
        raise HTTPException(status_code=500, detail="LLM returned no sub-genres")

    hints = load_hints(cfg.base_dir)
    for sg in sub_genres:
        if not sg.get("description"):
            sg["description"] = hints.get(sg["path"], "")

    return {
        "genre_prefix": genre_prefix,
        "sub_genres": sub_genres,
        "books": books_data,
        "total_books": len(rows),
    }


@books_router.post("/genres/expand/assign")
async def expand_genre_assign(request: Request):
    """Phase 2: assign one batch of books to the suggested sub-genres."""
    from backend.llm.factory import get_provider
    from backend.llm.prompts import build_genre_assign_prompt
    import json as _json
    import asyncio

    body = await request.json()
    genre_prefix = body.get("genre_prefix", "").strip()
    sub_genres = body.get("sub_genres", [])
    books = body.get("books", [])

    if not genre_prefix or not sub_genres or not books:
        raise HTTPException(status_code=422, detail="genre_prefix, sub_genres and books are required")

    cfg: AppConfig = request.app.state.config
    provider = get_provider(cfg.llms.extraction_model)
    assign_prompt = build_genre_assign_prompt(genre_prefix, sub_genres, books, language=cfg.content_language)

    loop = asyncio.get_event_loop()
    assign_raw = await loop.run_in_executor(None, lambda: provider.complete(assign_prompt, max_tokens=2048))

    raw = (assign_raw or "").strip()
    start = raw.find("{"); end = raw.rfind("}") + 1
    if start == -1 or end <= start:
        raise HTTPException(status_code=500, detail=f"LLM returned no valid JSON: {raw[:200]!r}")

    try:
        assignments = _json.loads(raw[start:end]).get("assignments", [])
    except _json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"JSON parse error ({exc}): {raw[:200]!r}")

    return {"assignments": assignments}


@books_router.post("/genres/expand/apply")
async def apply_genre_expansion(request: Request):
    """Batch-update genre_paths and save sub-genre hints."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.genre_hints import patch_hints
    from sqlmodel import select

    body = await request.json()
    sub_genres = body.get("sub_genres", [])
    cfg: AppConfig = request.app.state.config

    hints_updates: dict[str, str] = {}
    updated = 0

    with get_core_session() as session:
        for sg in sub_genres:
            path = sg.get("path", "")
            description = sg.get("description", "")
            if description and path:
                hints_updates[path] = description
            for bid in sg.get("book_ids", []):
                book = session.exec(select(Book).where(Book.id == bid)).first()
                if book:
                    book.genre_path = path
                    session.add(book)
                    updated += 1
        session.commit()

    if hints_updates:
        patch_hints(cfg.base_dir, hints_updates)

    return {"updated": updated}


@books_router.post("/upload")
async def upload_book(file: UploadFile, request: Request):
    from backend.ingestion.extractor import SUPPORTED_FORMATS
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )
    cfg: AppConfig = request.app.state.config
    dest_dir = cfg.storage.watch_folders[0] if cfg.storage.watch_folders else cfg.storage.books_root
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(file.filename).stem
    dest = dest_dir / file.filename
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{stem}_{counter}{ext}"
        counter += 1
    dest.write_bytes(await file.read())
    return {"status": "queued", "filename": dest.name}


@books_router.get("/{uuid}")
def get_book(uuid: str):
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select
    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == uuid)).first()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        return book.model_dump()


@books_router.get("/{uuid}/cover")
def get_book_cover(uuid: str, request: Request):
    cfg: AppConfig = request.app.state.config
    cover_path = cfg.storage.assets / "covers" / f"{uuid}.jpg"
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover not available")
    return FileResponse(str(cover_path), media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


@books_router.get("/{uuid}/file")
def get_book_file(uuid: str, mode: str = "download", request: Request = None):
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select
    import mimetypes

    cfg: AppConfig = request.app.state.config
    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == uuid)).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    rel = book.relative_path
    file_path = Path(rel) if Path(rel).is_absolute() else cfg.storage.books_root / rel
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    mime, _ = mimetypes.guess_type(str(file_path))
    mime = mime or "application/octet-stream"
    disposition = "inline" if mode == "inline" else f'attachment; filename="{file_path.name}"'
    return FileResponse(str(file_path), media_type=mime,
                        headers={"Content-Disposition": disposition})


@books_router.post("/{uuid}/open")
def open_book_in_system(uuid: str, request: Request):
    import subprocess, platform
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select

    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="System open only available on localhost")

    cfg: AppConfig = request.app.state.config
    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == uuid)).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    rel = book.relative_path
    file_path = Path(rel) if Path(rel).is_absolute() else cfg.storage.books_root / rel
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    cmd = "open" if platform.system() == "Darwin" else "xdg-open"
    subprocess.Popen([cmd, str(file_path)])
    return {"status": "opened"}


@config_router.get("")
def get_config(request: Request):
    import json
    path = request.app.state.config_path
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # Inject runtime capability flags
    try:
        import ebooklib  # noqa: F401
        epub_available = True
    except ImportError:
        epub_available = False
    data["capabilities"] = {"epub_export": epub_available}
    return data


@config_router.put("")
async def update_config(request: Request):
    import json
    from copy import deepcopy

    path = Path(request.app.state.config_path)
    current = json.loads(path.read_text(encoding="utf-8"))
    patch = await request.json()

    def deep_merge(base: dict, override: dict) -> dict:
        result = deepcopy(base)
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(result.get(k), dict):
                result[k] = deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    merged = deep_merge(current, patch)
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")

    # Reload config into app.state
    new_cfg = load_config(path)
    request.app.state.config = new_cfg
    return merged


@user_data_router.delete("")
def clear_user_data(request: Request):
    cfg: AppConfig = request.app.state.config
    reset_activity_db(cfg.storage.user_activity_db)
    return JSONResponse(status_code=204, content=None)


@reindex_router.post("")
def trigger_reindex(request: Request):
    from backend.fingerprint import write_fingerprint
    cfg: AppConfig = request.app.state.config
    emb = cfg.llms.embedding_model
    fp_path = cfg.base_dir / ".library_fingerprint.json"
    write_fingerprint(fp_path, emb.model_name, emb.dimension, book_count=0)
    request.app.state.index_stale = False
    return {"status": "reindex_triggered"}


from backend.ingestion.log_store import get_logs


@ingestion_router.get("/logs")
def ingestion_logs():
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select
    logs = get_logs()
    uuids = [l["uuid"] for l in logs if l.get("uuid")]
    if uuids:
        with get_core_session() as session:
            books = session.exec(select(Book).where(Book.id.in_(uuids))).all()
        fmt_map = {b.id: b.file_format for b in books}
        for log in logs:
            log["file_format"] = fmt_map.get(log["uuid"])
    return logs


@ingestion_router.post("")
async def ingest(request: Request):
    body = await request.json()
    file_path = body.get("file_path")
    if not file_path:
        raise HTTPException(status_code=422, detail="file_path is required")
    from backend.ingestion.pipeline import ingest_file
    result = ingest_file(file_path, request.app.state.config)
    return result.__dict__


@books_router.delete("/{uuid}")
def delete_book(uuid: str, delete_file: bool = False, request: Request = None):
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select
    import logging

    cfg: AppConfig = request.app.state.config
    vs = request.app.state.vector_store

    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == uuid)).first()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        rel = book.relative_path
        session.delete(book)
        session.commit()

    try:
        vs.delete_document(uuid)
    except Exception as e:
        logging.getLogger(__name__).warning("ChromaDB delete failed for %s: %s", uuid, e)

    cover = cfg.storage.assets / "covers" / f"{uuid}.jpg"
    cover.unlink(missing_ok=True)

    if delete_file:
        file_path = Path(rel) if Path(rel).is_absolute() else cfg.storage.books_root / rel
        try:
            file_path.unlink(missing_ok=True)
            _cleanup_empty_dirs(file_path.parent, cfg.storage.books_root)
        except Exception as e:
            logging.getLogger(__name__).warning("File delete failed for %s: %s", rel, e)

    return {"status": "removed", "uuid": uuid}


def _cleanup_empty_dirs(start: Path, stop: Path) -> None:
    p = start
    while p != stop and p != p.parent:
        try:
            p.rmdir()
            p = p.parent
        except OSError:
            break


@books_router.put("/{uuid}")
async def update_book(uuid: str, request: Request):
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.ingestion.file_mover import move_to_library, genre_to_dir
    from sqlmodel import select
    import json, logging

    cfg: AppConfig = request.app.state.config
    vs = request.app.state.vector_store
    body = await request.json()

    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == uuid)).first()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        old_genre = book.genre_path or ""
        new_genre = body.get("genre_path", old_genre)
        old_rel = book.relative_path

        # Move file if genre changed
        if new_genre != old_genre:
            file_path = Path(old_rel) if Path(old_rel).is_absolute() else cfg.storage.books_root / old_rel
            if file_path.exists():
                new_rel = move_to_library(file_path, new_genre, cfg.storage.books_root)
                if new_rel is None:
                    raise HTTPException(status_code=500, detail="File move failed")
                _cleanup_empty_dirs(file_path.parent, cfg.storage.books_root)
                book.relative_path = new_rel
            # else: file missing — update metadata only

        if "title" in body:
            book.title = body["title"]
        if "author" in body:
            book.author = body["author"] or None
        if "summary" in body:
            book.summary = body["summary"]
        if "genre_path" in body:
            book.genre_path = body["genre_path"]
        if "tags" in body:
            book.tags_json = json.dumps(body["tags"], ensure_ascii=False)

        from datetime import datetime
        book.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(book)
        result = book.model_dump()

    try:
        vs.update_metadata(uuid, {
            "title": result.get("title") or "",
            "author": result.get("author") or "",
            "genre_path": result.get("genre_path") or "",
        })
    except Exception as e:
        logging.getLogger(__name__).warning("Vector store metadata update failed: %s", e)

    return result


def _reclassify_book_sync(uuid: str, cfg, vs) -> dict | None:
    """Core reclassify logic — synchronous, safe to call from threads."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.ingestion.extractor import extract_text
    from backend.ingestion.file_mover import move_to_library
    from backend.llm.factory import get_provider
    from sqlmodel import select
    import json, logging, ast

    log = logging.getLogger(__name__)

    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == uuid)).first()
        if not book:
            return None
        rel = book.relative_path
        old_genre = book.genre_path or ""

    file_path = Path(rel) if Path(rel).is_absolute() else cfg.storage.books_root / rel
    if not file_path.exists():
        log.warning("Reclassify skipped — file not found: %s", rel)
        return None

    try:
        text = extract_text(file_path, max_pages=cfg.search.max_pages_to_analyze, use_ocr=False)
    except Exception as e:
        log.warning("Reclassify text extract failed for %s: %s", uuid, e)
        return None

    with get_core_session() as session:
        existing_genres = list(session.exec(
            select(Book.genre_path).where(Book.genre_path != None)
        ).all())

    language = getattr(cfg, 'content_language', 'en')
    provider = get_provider(cfg.llms.extraction_model)
    try:
        metadata = provider.extract_metadata(
            text, existing_genres=existing_genres,
            filename_hint=file_path.stem if not text.strip() else None,
            language=language
        )
    except Exception as e:
        log.warning("Reclassify LLM failed for %s: %s", uuid, e)
        return None

    tags_raw = metadata.get("tags", [])
    if isinstance(tags_raw, str):
        try:
            tags_raw = ast.literal_eval(tags_raw)
        except Exception:
            tags_raw = [tags_raw]

    def _coerce(v):
        if isinstance(v, list): return " > ".join(str(x) for x in v)
        return v or ""

    import re as _re
    llm_genre = _coerce(metadata.get("genre_path"))
    # Don't fall back to old genre if it's English or Simplified Chinese (needs fixing)
    old_genre_is_bad = bool(_re.search(r'[A-Za-z]', old_genre)) or bool(
        _re.search(r'[运动医饮艺绘经传临]', old_genre))
    new_genre = llm_genre or (old_genre if not old_genre_is_bad else "")

    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == uuid)).first()
        if not book:
            return None

        if new_genre and new_genre != (book.genre_path or ""):
            if file_path.exists():
                new_rel = move_to_library(file_path, new_genre, cfg.storage.books_root)
                if new_rel:
                    _cleanup_empty_dirs(file_path.parent, cfg.storage.books_root)
                    book.relative_path = new_rel
                    file_path = cfg.storage.books_root / new_rel

        book.title = _coerce(metadata.get("title")) or book.title or ""
        book.author = _coerce(metadata.get("author")) or book.author or None
        book.summary = _coerce(metadata.get("summary")) or book.summary or ""
        book.genre_path = new_genre
        book.tags_json = json.dumps(
            list(dict.fromkeys(tags_raw)) if isinstance(tags_raw, list) else [],
            ensure_ascii=False
        )
        from datetime import datetime
        book.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(book)
        result = book.model_dump()

    try:
        vs.update_metadata(uuid, {
            "title": result.get("title") or "",
            "author": result.get("author") or "",
            "genre_path": result.get("genre_path") or "",
        })
    except Exception as e:
        log.warning("VS update failed for %s: %s", uuid, e)

    return result


@books_router.post("/{uuid}/suggest-genre")
async def suggest_genre(uuid: str, request: Request):
    """Ask the LLM to pick the best genre from existing ones, or suggest a new one."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from backend.llm.factory import get_provider
    from backend.llm.prompts import build_genre_suggest_prompt
    from sqlmodel import select

    cfg: AppConfig = request.app.state.config

    with get_core_session() as session:
        book = session.exec(select(Book).where(Book.id == uuid)).first()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        existing_genres = sorted({
            g for g in session.exec(select(Book.genre_path).where(Book.genre_path.isnot(None))).all()
            if g
        })

    provider = get_provider(cfg.llms.extraction_model)
    prompt = build_genre_suggest_prompt(
        title=book.title,
        summary=book.summary or "",
        existing_genres=existing_genres,
        language=cfg.content_language,
    )

    import json as _json
    from backend.genre_hints import patch_hints
    try:
        raw = provider.complete(prompt, max_tokens=512).strip()
        # Expect JSON: {"genre_path": "...", "is_new": true/false, "description": "..."}
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1:
            raw = raw[start:end]
        try:
            data = _json.loads(raw)
            suggested = data.get("genre_path", raw)
            is_new = data.get("is_new", suggested not in existing_genres)
            description = data.get("description", "")
        except _json.JSONDecodeError:
            suggested = raw.strip().strip('"')
            is_new = suggested not in existing_genres
            description = ""
        # Auto-save description for new genres
        if is_new and suggested and description:
            patch_hints(cfg.base_dir, {suggested: description})
        return {"suggested_genre": suggested, "is_new": is_new, "description": description}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM suggest failed: {e}")


@books_router.post("/{uuid}/reclassify")
async def reclassify_book(uuid: str, request: Request):
    """Re-run LLM metadata extraction on an existing book using the current prompt."""
    cfg: AppConfig = request.app.state.config
    vs = request.app.state.vector_store
    result = await asyncio.to_thread(_reclassify_book_sync, uuid, cfg, vs)
    if result is None:
        raise HTTPException(status_code=404, detail="Book not found or file missing")
    return result


@books_router.post("/reclassify-all")
async def reclassify_all_books(request: Request):
    """Background thread: re-run LLM extraction on every book in the library."""
    from backend.db.core import get_core_session
    from backend.models.book import Book
    from sqlmodel import select
    import logging

    cfg: AppConfig = request.app.state.config
    vs = request.app.state.vector_store

    with get_core_session() as session:
        uuids = [b.id for b in session.exec(select(Book)).all()]

    def _run_all():
        log = logging.getLogger(__name__)
        for i, uid in enumerate(uuids, 1):
            log.info("Reclassify %d/%d: %s", i, len(uuids), uid)
            try:
                _reclassify_book_sync(uid, cfg, vs)
            except Exception as e:
                log.warning("Reclassify failed for %s: %s", uid, e)

    asyncio.create_task(asyncio.to_thread(_run_all))
    return {"status": "started", "total": len(uuids)}


@folders_router.get("")
def list_folders(request: Request):
    cfg: AppConfig = request.app.state.config
    from backend.models.book import Book
    from backend.db.core import get_core_session
    from sqlmodel import select, func

    with get_core_session() as session:
        total_books = session.exec(select(func.count()).select_from(Book)).one()

    watch_set = {str(p) for p in cfg.storage.watch_folders}
    ext = {".pdf", ".epub", ".txt", ".md"}
    folders = []
    for p in cfg.storage.pdf_roots:
        if p.exists():
            supported = [f for f in p.rglob("*") if f.suffix.lower() in ext and ".folio" not in f.parts]
        else:
            supported = []
        folders.append({
            "path": str(p),
            "exists": p.exists(),
            "total_files": len(supported),
            "watched": str(p) in watch_set,
        })
    return {"folders": folders, "total_indexed": total_books}


@folders_router.post("/scan")
async def scan_folders(request: Request):
    cfg: AppConfig = request.app.state.config
    from backend.watcher import scan_all
    # Run in thread so it doesn't block the event loop
    asyncio.create_task(asyncio.to_thread(scan_all, cfg.storage.pdf_roots, cfg))
    # Count pending files
    from backend.models.book import Book
    from backend.db.core import get_core_session
    from sqlmodel import select, func
    ext = {".pdf", ".epub", ".txt", ".md"}
    pending = 0
    with get_core_session() as session:
        known = set(session.exec(select(Book.relative_path)).all())
    for folder in cfg.storage.pdf_roots:
        if folder.exists():
            for f in folder.rglob("*"):
                if f.suffix.lower() not in ext or ".folio" in f.parts:
                    continue
                try:
                    rel = str(f.relative_to(cfg.storage.books_root))
                except ValueError:
                    rel = str(f)
                if rel not in known:
                    pending += 1
    return {"status": "started", "pending_files": pending}


@folders_router.post("/scan-path")
async def scan_custom_path(request: Request):
    cfg: AppConfig = request.app.state.config
    body = await request.json()
    raw = body.get("path", "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="path is required")
    folder = Path(raw).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory not found: {folder}")

    from backend.watcher import scan_all
    asyncio.create_task(asyncio.to_thread(scan_all, [folder], cfg))

    ext = {".pdf", ".epub", ".txt", ".md"}
    pending = sum(
        1 for f in folder.rglob("*")
        if f.suffix.lower() in ext and ".folio" not in f.parts
    )
    return {"status": "started", "pending_files": pending, "path": str(folder)}


from backend.routers.analysis import router as analysis_router
from backend.routers.chat import router as chat_router
from backend.routers.tts import router as tts_router

app.include_router(health_router)
app.include_router(search_router)
app.include_router(books_router)
app.include_router(analysis_router)
app.include_router(chat_router)
app.include_router(tts_router)
app.include_router(config_router)
app.include_router(user_data_router)
app.include_router(reindex_router)
app.include_router(ingestion_router)
app.include_router(folders_router)

# Serve built frontend — must come AFTER all API routers
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        file = _DIST / full_path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_DIST / "index.html"))
