"""Abstract base class for LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# Pricing per million tokens (USD) — Claude Sonnet 4.6
PRICING = {
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_write": 3.75,   # 1.25x input
        "cache_read": 0.30,    # 0.1x input
    },
    "claude-sonnet-4-20250514": {
        "input": 3.0,
        "output": 15.0,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-opus-4-6": {
        "input": 5.0,
        "output": 25.0,
        "cache_write": 6.25,
        "cache_read": 0.50,
    },
}


@dataclass
class LLMResponse:
    """Response from an LLM API call."""
    content: list[dict[str, Any]]  # Content blocks (text, tool_use)
    stop_reason: str  # "end_turn", "tool_use", "max_tokens"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    model: str = ""
    raw_response: Any = None

    @property
    def text_content(self) -> str:
        """Extract all text content from response (excludes reasoning blocks)."""
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

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens including cached ones."""
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    @property
    def cost_usd(self) -> float:
        """Calculate cost in USD for this response.

        Anthropic billing:
        - input_tokens: non-cached input tokens (billed at input rate)
        - cache_creation_input_tokens: newly cached (billed at cache_write rate)
        - cache_read_input_tokens: read from cache (billed at cache_read rate)
        - output_tokens: billed at output rate
        """
        pricing = PRICING.get(self.model)
        if not pricing:
            return 0.0  # No pricing info for this model (local/free)
        cost = (
            self.input_tokens * pricing["input"] / 1_000_000
            + self.output_tokens * pricing["output"] / 1_000_000
            + self.cache_creation_input_tokens * pricing["cache_write"] / 1_000_000
            + self.cache_read_input_tokens * pricing["cache_read"] / 1_000_000
        )
        return cost


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
