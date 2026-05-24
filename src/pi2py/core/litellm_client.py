from __future__ import annotations

import logging
import os
from typing import Any, Protocol

from pi2py.core.messages import ChatMessage
from pi2py.core.tools import Tool


class LLMClient(Protocol):
    async def complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[Tool],
        temperature: float | None = None,
    ) -> ChatMessage: ...


class LiteLLMClient:
    async def complete(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[Tool],
        temperature: float | None = None,
    ) -> ChatMessage:
        _quiet_litellm_optional_dependency_warnings()
        from litellm import acompletion

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [message.to_litellm() for message in messages],
        }
        if tools:
            kwargs["tools"] = [tool.to_openai_tool() for tool in tools]
            kwargs["tool_choice"] = "auto"
        if temperature is not None:
            kwargs["temperature"] = temperature

        response = await acompletion(**kwargs)
        message = response.choices[0].message
        return ChatMessage.from_litellm(message)


def _quiet_litellm_optional_dependency_warnings() -> None:
    if not os.environ.get("LITELLM_LOG"):
        os.environ["LITELLM_LOG"] = "ERROR"
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
