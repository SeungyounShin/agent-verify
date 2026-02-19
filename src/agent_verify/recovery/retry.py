"""R1: Retry in context - append failure feedback and continue."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import RecoveryStrategy

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.verification.base import VerificationResult


class RetryInContext(RecoveryStrategy):
    """R1: Append failure feedback to current context and retry."""

    @property
    def strategy_name(self) -> str:
        return "retry_in_context"

    def recover(self, context: Context, verification: VerificationResult, task: Task) -> Context:
        feedback = (
            f"VERIFICATION FAILED. Please fix the issues and try again.\n\n"
            f"Failure details:\n{verification.message}"
        )
        context.add_user_message(feedback)
        context.recovery_count += 1
        context.is_complete = False
        return context
