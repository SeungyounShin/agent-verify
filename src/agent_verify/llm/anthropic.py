"""Anthropic Claude LLM client with tool use and prompt caching support."""

from __future__ import annotations

import copy
from typing import Any

import anthropic

from .base import LLMClient, LLMResponse


class AnthropicClient(LLMClient):
    """Claude API client with tool use and prompt caching support.

    Caching strategy:
    - System prompt: always cached (static across all turns)
    - Tools: always cached (static across all turns)
    - Conversation history: cache breakpoint on the second-to-last user turn,
      so all prior context is reused on each subsequent API call.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.client = anthropic.Anthropic()

    def generate(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> LLMResponse:
        # Build system prompt with cache_control on the static part
        system_blocks = None
        if system:
            system_blocks = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        # Add cache_control to the last tool definition (tools are static)
        cached_tools = None
        if tools:
            cached_tools = [dict(t) for t in tools]
            cached_tools[-1] = {
                **cached_tools[-1],
                "cache_control": {"type": "ephemeral"},
            }

        # Add cache breakpoint on conversation history
        cached_messages = _add_cache_breakpoints(messages)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": cached_messages,
        }
        if system_blocks:
            kwargs["system"] = system_blocks
        if cached_tools:
            kwargs["tools"] = cached_tools

        response = self.client.messages.create(**kwargs)

        content = []
        for block in response.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        # Extract cache token info from usage
        usage = response.usage
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

        return LLMResponse(
            content=content,
            stop_reason=response.stop_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
            model=response.model,
            raw_response=response,
        )


def _add_cache_breakpoints(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add cache_control breakpoint to conversation history.

    Strategy: put a cache breakpoint on the second-to-last user/tool_result
    message. This way, everything before that message is cached, and only
    the last exchange is newly processed on each turn.
    """
    if len(messages) < 4:
        # Too few messages for caching to help
        return messages

    # Deep copy to avoid mutating the original context
    msgs = copy.deepcopy(messages)

    # Find the second-to-last user message (going backwards)
    user_msg_indices = [
        i for i, m in enumerate(msgs) if m["role"] == "user"
    ]

    if len(user_msg_indices) >= 2:
        target_idx = user_msg_indices[-2]
        _inject_cache_control(msgs[target_idx])

    return msgs


def _inject_cache_control(message: dict[str, Any]) -> None:
    """Inject cache_control into a message's content."""
    content = message.get("content")

    if isinstance(content, str):
        # Convert string content to block format with cache_control
        message["content"] = [
            {
                "type": "text",
                "text": content,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    elif isinstance(content, list) and content:
        # Add cache_control to the last content block
        last_block = content[-1]
        if isinstance(last_block, dict):
            last_block["cache_control"] = {"type": "ephemeral"}
