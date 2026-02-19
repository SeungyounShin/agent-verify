"""Base verification classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.llm.base import LLMClient


@dataclass
class VerificationResult:
    """Result of a verification check."""
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    token_cost: int = 0  # tokens consumed by verification


class Verifier(ABC):
    """Abstract base class for verification strategies."""

    @abstractmethod
    def verify(self, context: Context, task: Task, llm_client: LLMClient | None = None) -> VerificationResult:
        """Run verification and return result."""
        ...

    @property
    @abstractmethod
    def method_name(self) -> str:
        """Human-readable name of this verification method."""
        ...
