from datetime import datetime
from dataclasses import dataclass, field, asdict
from collections import deque

_MAX_LOGS = 100
_logs: deque = deque(maxlen=_MAX_LOGS)


@dataclass
class IngestionLog:
    uuid: str
    title: str
    status: str
    message: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def append_log(entry: IngestionLog) -> None:
    _logs.appendleft(entry)


def get_logs() -> list[dict]:
    return [asdict(e) for e in _logs]
