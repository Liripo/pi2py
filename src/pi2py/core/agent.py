from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pi2py.core.litellm_client import LLMClient, LiteLLMClient
from pi2py.core.messages import AgentEvent, ChatMessage
from pi2py.core.session import Session, SessionStore
from pi2py.core.tools import Tool, create_default_tools

EventHandler = Callable[[AgentEvent], None]


@dataclass
class AgentConfig:
    model: str = "gpt-4o-mini"
    cwd: Path = Path.cwd()
    system_prompt: str | None = None
    max_turns: int = 20
    temperature: float | None = None
    allow_bash: bool = True


class Agent:
    def __init__(
        self,
        config: AgentConfig | None = None,
        *,
        tools: list[Tool] | None = None,
        llm: LLMClient | None = None,
        session_store: SessionStore | None = None,
    ) -> None:
        self.config = config or AgentConfig()
        self.cwd = self.config.cwd.resolve()
        self.tools = tools if tools is not None else create_default_tools(self.cwd, allow_bash=self.config.allow_bash)
        self.llm = llm or LiteLLMClient()
        self.session_store = session_store
        self.session = session_store.load() if session_store else Session()
        if not self.session.messages:
            self.session.messages.append(ChatMessage(role="system", content=self._system_prompt()))

    async def run(self, prompt: str) -> str:
        last = ""
        async for event in self.run_events(prompt):
            if event.type == "assistant_message":
                last = str(event.data.get("content") or "")
        return last

    async def run_events(self, prompt: str) -> AsyncIterator[AgentEvent]:
        user_message = ChatMessage(role="user", content=prompt)
        self.session.messages.append(user_message)
        yield AgentEvent("message", {"role": "user", "content": prompt})

        for _ in range(self.config.max_turns):
            yield AgentEvent("llm_start", {"model": self.config.model})
            assistant = await self.llm.complete(
                model=self.config.model,
                messages=self.session.messages,
                tools=self.tools,
                temperature=self.config.temperature,
            )
            self.session.messages.append(assistant)
            yield AgentEvent("assistant_message", {"content": assistant.content or "", "tool_calls": assistant.tool_calls or []})

            if not assistant.tool_calls:
                self._save()
                yield AgentEvent("agent_end", {"reason": "stop"})
                return

            for call in assistant.tool_calls:
                tool_result = await self._execute_tool_call(call)
                self.session.messages.append(tool_result)
                yield AgentEvent(
                    "tool_result",
                    {"name": tool_result.name, "tool_call_id": tool_result.tool_call_id, "content": tool_result.content},
                )

        self._save()
        yield AgentEvent("agent_end", {"reason": "max_turns"})

    async def _execute_tool_call(self, call: dict[str, Any]) -> ChatMessage:
        function = call.get("function") or {}
        name = function.get("name")
        raw_args = function.get("arguments") or "{}"
        call_id = call.get("id")
        tool = next((candidate for candidate in self.tools if candidate.name == name), None)
        if tool is None:
            content = f"未知工具：{name}"
            return ChatMessage(role="tool", name=name, tool_call_id=call_id, content=content)

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            if not isinstance(args, dict):
                raise ValueError("工具参数必须是 JSON 对象")
            content = await tool.handler(args)
        except Exception as exc:
            content = f"工具 {name} 执行失败：{exc}"

        return ChatMessage(role="tool", name=name, tool_call_id=call_id, content=content)

    def _save(self) -> None:
        if self.session_store:
            self.session_store.save(self.session)

    def _system_prompt(self) -> str:
        if self.config.system_prompt:
            return self.config.system_prompt
        tool_names = ", ".join(tool.name for tool in self.tools)
        cwd = self.cwd.as_posix()
        return (
            "你是 pi2py，一个运行在终端里的简洁 Coding Agent。"
            "需要时使用工具检查和修改文件，简要说明关键结果，避免无关改动。"
            f"可用工具：{tool_names}。当前工作目录：{cwd}。"
        )
