from __future__ import annotations

from typer.testing import CliRunner

from pi2py import __version__
from pi2py.cli import _handle_model_command, app
from pi2py.core.agent import Agent, AgentConfig
from pi2py.core.settings import SettingsStore


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


def test_tools_output_is_formatted() -> None:
    result = CliRunner().invoke(app, ["tools", "--model", "deepseek/deepseek-v4-flash"])

    assert result.exit_code == 0
    assert "pi2py tools" in result.output
    assert "deepseek/deepseek-v4-flash" in result.output
    assert "read" in result.output


def test_model_command_updates_agent_and_settings(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "config.json"
    monkeypatch.setattr(SettingsStore, "default_path", staticmethod(lambda: settings_path))
    agent = Agent(AgentConfig(model="gpt-4o-mini", cwd=tmp_path))

    _handle_model_command(agent, "/model deepseek/deepseek-v4-flash")

    assert agent.config.model == "deepseek/deepseek-v4-flash"
    assert SettingsStore().load().model == "deepseek/deepseek-v4-flash"
