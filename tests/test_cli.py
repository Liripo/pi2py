from __future__ import annotations

from typer.testing import CliRunner

from pi2py import __version__
from pi2py.cli import app


def test_short_help_option_hides_removed_flags() -> None:
    result = CliRunner().invoke(app, ["-h"])

    assert result.exit_code == 0
    assert "--print" in result.output
    assert "--session" not in result.output
    assert "--bash" not in result.output


def test_version_comes_from_package_metadata() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_short_version_option() -> None:
    result = CliRunner().invoke(app, ["-v"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__
