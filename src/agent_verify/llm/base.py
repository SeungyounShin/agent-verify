"""Abstract base class for LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    """Response from an LLM API call."""
    content: list[dict[str, Any]]  # Content blocks (text, tool_use)
    stop_reason: str  # "end_turn", "tool_use", "max_tokens"
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    raw_response: Any = None

    @property
    def text_content(self) -> str:
        """Extract all text content from response."""
        parts = []
        for block in self.content:
            if block.get("type") == "text":
                parts.append(block["text"])
        return "\n".join(parts)

    @property
    def tool_uses(self) -> list[dict[str, Any]]:
        """Extract all tool use blocks from response."""
        return [b for b in self.content if b.get("type") == "tool_use"]

    @property
    def has_tool_use(self) -> bool:
        return len(self.tool_uses) > 0


class LLMClient(ABC):
    """Abstract base for LLM API clients."""

    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        ...
