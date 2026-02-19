"""Base tool classes for the agent harness."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Abstract base class for agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return string output."""
        ...

    def to_api_schema(self) -> dict[str, Any]:
        """Convert to Anthropic tool API format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolSet:
    """Registry and dispatcher for agent tools."""

    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def execute(self, name: str, **kwargs: Any) -> str:
        return self.get(name).execute(**kwargs)

    def to_api_schemas(self) -> list[dict[str, Any]]:
        return [t.to_api_schema() for t in self._tools.values()]

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
