from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pi2py.core.messages import ChatMessage


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    messages: list[ChatMessage] = field(default_factory=list)


class SessionStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    @staticmethod
    def default_dir() -> Path:
        return Path.home() / ".pi2py" / "sessions"

    @classmethod
    def create_default(cls, cwd: Path) -> "SessionStore":
        safe = str(cwd.resolve()).replace(":", "").replace("\\", "_").replace("/", "_")
        path = cls.default_dir() / safe / f"{datetime.now():%Y%m%d-%H%M%S}.json"
        return cls(path)

    def load(self) -> Session:
        if not self.path or not self.path.exists():
            return Session()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return Session(
            id=raw["id"],
            created_at=raw["created_at"],
            messages=[ChatMessage(**message) for message in raw.get("messages", [])],
        )

    def save(self, session: Session) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": session.id,
            "created_at": session.created_at,
            "messages": [asdict(message) for message in session.messages],
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

