"""一个可用的 pi-agent 风格 Python Coding Agent。"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib

__all__ = ["__version__"]


def _read_version() -> str:
    try:
        return version("pi2py")
    except PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproject.exists():
            with pyproject.open("rb") as file:
                return str(tomllib.load(file)["project"]["version"])
        return "0.0.0"

__version__ = _read_version()
