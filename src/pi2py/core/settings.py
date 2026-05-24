from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class AppSettings:
    model: str = DEFAULT_MODEL


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        return Path.home() / ".pi2py" / "config.json"

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings()
        model = raw.get("model")
        return AppSettings(model=model if isinstance(model, str) and model.strip() else DEFAULT_MODEL)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"model": settings.model}, indent=2, ensure_ascii=False), encoding="utf-8")

    def save_model(self, model: str) -> AppSettings:
        settings = self.load()
        settings.model = model
        self.save(settings)
        return settings
