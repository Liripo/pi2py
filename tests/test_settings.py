from __future__ import annotations

from pi2py.core.settings import DEFAULT_MODEL, AppSettings, SettingsStore


def test_settings_store_defaults_to_builtin_model(tmp_path) -> None:
    store = SettingsStore(tmp_path / "config.json")

    assert store.load().model == DEFAULT_MODEL


def test_settings_store_persists_model(tmp_path) -> None:
    store = SettingsStore(tmp_path / "config.json")

    store.save(AppSettings(model="deepseek/deepseek-v4-flash"))

    assert store.load().model == "deepseek/deepseek-v4-flash"
