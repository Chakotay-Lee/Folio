import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class FingerprintData:
    embedding_model: str
    embedding_dimension: int
    created_at: str
    book_count: int


def read_fingerprint(path: Path) -> Optional[FingerprintData]:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return FingerprintData(
        embedding_model=raw["embedding_model"],
        embedding_dimension=raw["embedding_dimension"],
        created_at=raw["created_at"],
        book_count=raw.get("book_count", 0),
    )


def write_fingerprint(path: Path, model: str, dimension: int, book_count: int) -> None:
    data = {
        "embedding_model": model,
        "embedding_dimension": dimension,
        "created_at": datetime.utcnow().isoformat(),
        "book_count": book_count,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def validate_fingerprint(fp_path: Path, model: str, dimension: int) -> bool:
    fp = read_fingerprint(fp_path)
    if fp is None:
        return True
    return fp.embedding_model == model and fp.embedding_dimension == dimension
