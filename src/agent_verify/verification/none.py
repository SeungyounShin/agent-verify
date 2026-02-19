"""V0: No verification - agent self-declares completion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import VerificationResult, Verifier

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.llm.base import LLMClient


class NoVerification(Verifier):
    """V0: No verification. Always passes."""

    @property
    def method_name(self) -> str:
        return "none"

    def verify(self, context: Context, task: Task, llm_client: LLMClient | None = None) -> VerificationResult:
        return VerificationResult(passed=True, message="No verification performed (V0 baseline)")
