from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event, text


_engine = None


def init_core_db(db_path: Path) -> None:
    global _engine
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{db_path}", echo=False)

    @event.listens_for(_engine, "connect")
    def set_wal(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    from backend.models.book import Book  # noqa: F401
    SQLModel.metadata.create_all(_engine)
    _run_migrations(_engine)


def _run_migrations(engine) -> None:
    """Add columns introduced after initial schema creation."""
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(books)"))}
        if "analysis_status" not in cols:
            conn.execute(text("ALTER TABLE books ADD COLUMN analysis_status TEXT NOT NULL DEFAULT 'none'"))
            conn.commit()


def get_core_session() -> Session:
    if _engine is None:
        raise RuntimeError("Core DB not initialised — call init_core_db() first")
    return Session(_engine)
