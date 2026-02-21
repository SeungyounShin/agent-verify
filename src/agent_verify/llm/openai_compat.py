"""OpenAI-compatible LLM client for vLLM, ollama, and other local servers.

Supports interleaved reasoning (thinking) for models like Qwen3/3.5.
vLLM returns reasoning in a separate `reasoning` field; we preserve it
across turns so the model can maintain chain-of-thought in multi-turn
tool-use conversations.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from openai import OpenAI

from .base import LLMClient, LLMResponse


class OpenAICompatClient(LLMClient):
    """OpenAI-compatible API client with tool use and reasoning support."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "dummy",
    ):
        self.model = model
        self.base_url = base_url
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.6,
    ) -> LLMResponse:
        # Build messages in OpenAI format
        oai_messages: list[dict[str, Any]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})

        for msg in messages:
            converted = _convert_message(msg)
            if isinstance(converted, list):
                oai_messages.extend(converted)
            else:
                oai_messages.append(converted)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": oai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if tools:
            kwargs["tools"] = [_to_openai_tool(t) for t in tools]

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        # Extract reasoning (vLLM puts <think> content here, separate from content)
        reasoning = getattr(message, "reasoning", None) or getattr(
            message, "reasoning_content", None
        )

        # Content (should be clean, without <think> tags if vLLM parsed correctly)
        raw_text = message.content or ""
        # Safety: strip any remaining <think> tags in case vLLM didn't parse them
        text = _strip_thinking(raw_text)

        # Build content blocks (Anthropic format for harness compatibility)
        content: list[dict[str, Any]] = []
        if text:
            content.append({"type": "text", "text": text})

        # Handle tool calls
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    tool_input = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_input = {"raw": tc.function.arguments}

                content.append({
                    "type": "tool_use",
                    "id": tc.id or f"call_{uuid.uuid4().hex[:8]}",
                    "name": tc.function.name,
                    "input": tool_input,
                })

        # Fallback: parse tool calls from text if model didn't use native calling
        if not message.tool_calls and tools and text:
            parsed = _try_parse_tool_call_from_text(text, tools)
            if parsed:
                content = parsed

        # Map stop reason
        stop_reason = "end_turn"
        if choice.finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif choice.finish_reason == "length":
            stop_reason = "max_tokens"

        # Token usage
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        # Store reasoning in content metadata so harness can pass it back
        # We attach it as a special block that _convert_message will pick up
        if reasoning:
            content.append({
                "type": "_reasoning",
                "reasoning": reasoning,
            })

        return LLMResponse(
            content=content,
            stop_reason=stop_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            raw_response=response,
        )


def _convert_message(msg: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
    """Convert Anthropic-format message to OpenAI format.

    Handles interleaved reasoning: if an assistant message contains a
    `_reasoning` block, it is forwarded as the `reasoning` field in the
    OpenAI assistant message so the model sees its own prior thinking.
    """
    role = msg["role"]
    content = msg.get("content", "")

    # --- Tool results (Anthropic: role=user with tool_result blocks) ---
    if role == "user" and isinstance(content, list):
        tool_results = [b for b in content if b.get("type") == "tool_result"]
        if tool_results:
            messages = []
            for tr in tool_results:
                tool_content = tr.get("content", "")
                if isinstance(tool_content, list):
                    tool_content = "\n".join(
                        b.get("text", "") for b in tool_content if b.get("type") == "text"
                    )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr.get("tool_use_id", "unknown"),
                    "content": str(tool_content),
                })
            return messages[0] if len(messages) == 1 else messages

        # Regular content blocks
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block["text"])
            elif isinstance(block, str):
                text_parts.append(block)
        return {"role": role, "content": "\n".join(text_parts)}

    # --- Assistant messages with tool_use and/or reasoning blocks ---
    if role == "assistant" and isinstance(content, list):
        text_parts = []
        tool_calls = []
        reasoning = None

        for block in content:
            if block.get("type") == "text":
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"]),
                    },
                })
            elif block.get("type") == "_reasoning":
                reasoning = block.get("reasoning")

        result: dict[str, Any] = {
            "role": "assistant",
            "content": "\n".join(text_parts) if text_parts else None,
        }
        if tool_calls:
            result["tool_calls"] = tool_calls
        # Include reasoning for interleaved thinking (vLLM / Qwen3 style)
        if reasoning:
            result["reasoning"] = reasoning
        return result

    # Simple text message
    if isinstance(content, str):
        return {"role": role, "content": content}

    return {"role": role, "content": str(content)}


def _to_openai_tool(anthropic_tool: dict[str, Any]) -> dict[str, Any]:
    """Convert Anthropic tool schema to OpenAI tool format."""
    schema = dict(anthropic_tool.get("input_schema", {}))
    schema.pop("cache_control", None)

    return {
        "type": "function",
        "function": {
            "name": anthropic_tool["name"],
            "description": anthropic_tool.get("description", ""),
            "parameters": schema,
        },
    }


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from model output (safety fallback)."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def _try_parse_tool_call_from_text(
    text: str, tools: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """Try to extract tool calls from text when model doesn't use native tool calling."""
    tool_names = {t["name"] for t in tools}

    json_pattern = r'\{[^{}]*"name"\s*:\s*"(\w+)"[^{}]*"(?:input|arguments)"\s*:\s*(\{[^}]*\})[^{}]*\}'
    matches = re.findall(json_pattern, text, re.DOTALL)

    if not matches:
        return None

    content = []
    for name, args_str in matches:
        if name not in tool_names:
            continue
        try:
            args = json.loads(args_str)
            content.append({
                "type": "tool_use",
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": name,
                "input": args,
            })
        except json.JSONDecodeError:
            continue

    return content if content else None
