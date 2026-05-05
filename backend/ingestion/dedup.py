import hashlib
import logging
from simhash import Simhash

logger = logging.getLogger(__name__)

DUPLICATE_THRESHOLD = 0.95


def _make_simhash(text: str) -> Simhash | None:
    try:
        return Simhash(text)
    except (OverflowError, ValueError, Exception) as e:
        logger.debug("Simhash failed (%s), using ASCII fallback", e)
        try:
            return Simhash(text.encode('ascii', errors='replace').decode('ascii'))
        except Exception:
            return None


def compute_simhash(text: str) -> str:
    sh = _make_simhash(text)
    if sh is not None:
        return str(sh.value)
    # Last-resort fallback: SHA-256 truncated to 64-bit
    return str(int(hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()[:16], 16))


def is_duplicate(text: str, existing_hashes: list[str], threshold: float = DUPLICATE_THRESHOLD) -> bool:
    if not existing_hashes:
        return False
    candidate = _make_simhash(text)
    if candidate is None:
        return False
    for h in existing_hashes:
        try:
            existing = Simhash(int(h))
            distance = candidate.distance(existing)
            similarity = 1.0 - distance / 64
            if similarity >= threshold:
                return True
        except (ValueError, TypeError):
            continue
    return False


def get_all_simhashes(session) -> list[str]:
    from sqlmodel import select
    from backend.models.book import Book
    results = session.exec(select(Book.simhash).where(Book.simhash.isnot(None))).all()
    return [r for r in results if r]
