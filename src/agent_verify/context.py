"""Context management for agent conversations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens


@dataclass
class Message:
    role: str  # "user", "assistant", "tool_result"
    content: Any  # str or list of content blocks
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    tool_name: str
    tool_input: dict[str, Any]
    tool_result: str
    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 0.0


@dataclass
class Context:
    """Manages the conversation context for an agent run."""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    start_time: float = field(default_factory=time.time)
    iteration_count: int = 0
    verification_count: int = 0
    recovery_count: int = 0
    is_complete: bool = False
    completion_reason: str = ""

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: Any) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_result(self, tool_use_id: str, content: str) -> None:
        self.messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content,
                }
            ],
        })

    def record_tool_call(self, tool_call: ToolCall) -> None:
        self.tool_calls.append(tool_call)

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def clone_fresh(self) -> Context:
        """Create a fresh context (for R3 fresh restart)."""
        return Context(start_time=self.start_time)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of this context for logging."""
        return {
            "message_count": len(self.messages),
            "tool_call_count": len(self.tool_calls),
            "token_usage": {
                "input": self.token_usage.input_tokens,
                "output": self.token_usage.output_tokens,
                "total": self.token_usage.total,
            },
            "elapsed_seconds": self.elapsed_seconds,
            "iteration_count": self.iteration_count,
            "verification_count": self.verification_count,
            "recovery_count": self.recovery_count,
            "is_complete": self.is_complete,
            "completion_reason": self.completion_reason,
        }
