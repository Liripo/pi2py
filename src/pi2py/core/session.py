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


@dataclass
class SessionInfo:
    path: Path
    id: str
    created_at: str
    message_count: int
    first_user_message: str = ""


class SessionStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    @staticmethod
    def default_dir() -> Path:
        return Path.home() / ".pi2py" / "sessions"

    @classmethod
    def _cwd_dir(cls, cwd: Path) -> Path:
        safe = str(cwd.resolve()).replace(":", "").replace("\\", "_").replace("/", "_")
        return cls.default_dir() / safe

    @classmethod
    def create_default(cls, cwd: Path) -> "SessionStore":
        dirpath = cls._cwd_dir(cwd)
        path = dirpath / f"{datetime.now():%Y%m%d-%H%M%S}.json"
        return cls(path)

    @classmethod
    def list_sessions(cls, cwd: Path) -> list[SessionInfo]:
        dirpath = cls._cwd_dir(cwd)
        if not dirpath.exists():
            return []
        results: list[SessionInfo] = []
        for f in sorted(dirpath.glob("*.json"), reverse=True):
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            messages = raw.get("messages") or []
            msg_count = len(messages)
            first_user = ""
            for msg in messages:
                if msg.get("role") == "user" and msg.get("content"):
                    first_user = msg["content"][:80]
                    break
            results.append(
                SessionInfo(
                    path=f,
                    id=raw.get("id", ""),
                    created_at=raw.get("created_at", ""),
                    message_count=msg_count,
                    first_user_message=first_user,
                )
            )
        return results

    @classmethod
    def find_by_id(cls, cwd: Path, session_id: str) -> SessionInfo | None:
        for info in cls.list_sessions(cwd):
            if info.id.startswith(session_id):
                return info
        return None

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

