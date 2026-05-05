from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
import uuid as _uuid


class ReadingProgress(SQLModel, table=True):
    __tablename__ = "reading_progress"

    book_id: str = Field(primary_key=True)
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    last_read_at: datetime = Field(default_factory=datetime.utcnow)


class Highlight(SQLModel, table=True):
    __tablename__ = "highlights"

    id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True)
    book_id: str = Field(index=True)
    page_number: int
    text: str
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
