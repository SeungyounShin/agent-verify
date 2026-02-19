"""R3: Fresh-context restart - Ralph-style clean restart."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import RecoveryStrategy

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.verification.base import VerificationResult


class FreshRestart(RecoveryStrategy):
    """R3: Start completely fresh context, preserving only filesystem state.

    Ralph-style: "No compaction, no degradation."
    - New context window
    - Filesystem + git state preserved (handled by harness)
    - Only the verification failure message is carried forward
    """

    @property
    def strategy_name(self) -> str:
        return "fresh_restart"

    def recover(self, context: Context, verification: VerificationResult, task: Task) -> Context:
        from agent_verify.context import Context as ContextClass

        new_context = ContextClass(start_time=context.start_time)
        # Carry over cumulative metrics
        new_context.token_usage = context.token_usage
        new_context.tool_calls = context.tool_calls
        new_context.iteration_count = context.iteration_count
        new_context.verification_count = context.verification_count
        new_context.recovery_count = context.recovery_count + 1

        # Minimal failure signal — only what failed, not the full history
        restart_message = (
            f"## Task\n{task.description}\n\n"
            f"## Previous Attempt Result\n"
            f"A previous attempt was made but verification failed:\n"
            f"{verification.message}\n\n"
            f"The workspace filesystem contains changes from the previous attempt. "
            f"You may inspect the current state of files and git history.\n\n"
            f"Please complete this task, addressing the issues identified above."
        )
        new_context.add_user_message(restart_message)

        return new_context
