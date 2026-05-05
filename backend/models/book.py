from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
import uuid as _uuid


class Book(SQLModel, table=True):
    __tablename__ = "books"

    id: str = Field(default_factory=lambda: str(_uuid.uuid4()), primary_key=True)
    relative_path: str = Field(unique=True, index=True)
    title: str
    author: Optional[str] = None
    genre_path: Optional[str] = None
    summary: Optional[str] = None
    tags_json: Optional[str] = None
    file_format: str
    file_size_bytes: int
    page_count: Optional[int] = None
    simhash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
