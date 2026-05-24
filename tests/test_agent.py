from __future__ import annotations

from pathlib import Path

import pytest

from pi2py.core.agent import Agent, AgentConfig
from pi2py.core.messages import ChatMessage
from pi2py.core.tools import create_default_tools


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *, model, messages, tools, temperature=None):
        self.calls += 1
        if self.calls == 1:
            return ChatMessage(
                role="assistant",
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read", "arguments": '{"path": "hello.txt"}'},
                    }
                ],
            )
        return ChatMessage(role="assistant", content="The file says hello.")


@pytest.mark.asyncio
async def test_agent_executes_tool_loop(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")
    agent = Agent(
        AgentConfig(model="fake", cwd=tmp_path),
        tools=create_default_tools(tmp_path, allow_bash=False),
        llm=FakeLLM(),
    )

    answer = await agent.run("read hello.txt")

    assert answer == "The file says hello."
    assert any(message.role == "tool" and "hello.txt" in (message.content or "") for message in agent.session.messages)

