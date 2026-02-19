"""Base recovery strategy classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.verification.base import VerificationResult


class RecoveryStrategy(ABC):
    """Abstract base class for failure recovery strategies."""

    @abstractmethod
    def recover(self, context: Context, verification: VerificationResult, task: Task) -> Context:
        """Recover from a verification failure and return updated context."""
        ...

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        ...
