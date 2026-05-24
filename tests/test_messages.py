from __future__ import annotations

from pi2py.core.messages import ChatMessage


def test_reasoning_content_round_trips_to_litellm() -> None:
    message = ChatMessage(role="assistant", content="答案", reasoning_content="推理内容")

    assert message.to_litellm()["reasoning_content"] == "推理内容"


def test_reasoning_content_is_preserved_from_litellm_message() -> None:
    message = ChatMessage.from_litellm(
        {
            "role": "assistant",
            "content": "答案",
            "reasoning_content": "推理内容",
        }
    )

    assert message.reasoning_content == "推理内容"
