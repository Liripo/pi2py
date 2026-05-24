from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ChatMessage:
    role: Role
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    reasoning_content: str | None = None

    def to_litellm(self) -> dict[str, Any]:
        data: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            data["content"] = self.content
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.name:
            data["name"] = self.name
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        if self.reasoning_content:
            data["reasoning_content"] = self.reasoning_content
        return data

    @classmethod
    def from_litellm(cls, data: Any) -> "ChatMessage":
        role = _get(data, "role") or "assistant"
        content = _get(data, "content")
        tool_calls = _get(data, "tool_calls")
        reasoning_content = _get(data, "reasoning_content")
        return cls(
            role=role,
            content=content,
            tool_calls=_normalize_tool_calls(tool_calls),
            reasoning_content=reasoning_content,
        )


@dataclass
class AgentEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _normalize_tool_calls(tool_calls: Any) -> list[dict[str, Any]] | None:
    if not tool_calls:
        return None
    normalized = []
    for call in tool_calls:
        call_id = _get(call, "id")
        call_type = _get(call, "type") or "function"
        function = _get(call, "function") or {}
        normalized.append(
            {
                "id": call_id,
                "type": call_type,
                "function": {
                    "name": _get(function, "name"),
                    "arguments": _get(function, "arguments") or "{}",
                },
            }
        )
    return normalized
