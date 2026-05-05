from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event


_engine = None


def init_activity_db(db_path: Path) -> None:
    global _engine
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{db_path}", echo=False)

    @event.listens_for(_engine, "connect")
    def set_wal(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    from backend.models.activity import ReadingProgress, Highlight  # noqa: F401
    SQLModel.metadata.create_all(_engine)


def get_activity_session() -> Session:
    if _engine is None:
        raise RuntimeError("Activity DB not initialised — call init_activity_db() first")
    return Session(_engine)


def reset_activity_db(db_path: Path) -> None:
    global _engine
    if _engine:
        _engine.dispose()
        _engine = None
    if db_path.exists():
        db_path.unlink()
    init_activity_db(db_path)
