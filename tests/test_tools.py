from __future__ import annotations

import pytest

from pi2py.core.tools import check_bash_safety, run_bash_command


def test_bash_safety_blocks_rm_rf_root() -> None:
    result = check_bash_safety("rm -rf /")

    assert not result.allowed
    assert result.reason == "rm -rf / is blocked"


def test_bash_safety_allows_non_rm_rf_commands() -> None:
    assert check_bash_safety("git status").allowed
    assert check_bash_safety("curl https://example.com").allowed
    assert check_bash_safety("echo hello | findstr hello").allowed
    assert check_bash_safety("rm -rf tmp").allowed


@pytest.mark.asyncio
async def test_run_bash_command_blocks_rm_rf(tmp_path) -> None:
    with pytest.raises(ValueError, match="rm -rf / is blocked"):
        await run_bash_command(tmp_path, "rm -rf /")
