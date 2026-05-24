"""一个最小可用的 pi 风格 Python Coding Agent。"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]


def _read_version() -> str:
    try:
        return version("pi2py")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _read_version()
