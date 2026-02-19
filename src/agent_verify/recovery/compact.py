"""R2: Compaction + retry - summarize context and continue with failure info."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import RecoveryStrategy

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.llm.base import LLMClient
    from agent_verify.verification.base import VerificationResult


COMPACTION_PROMPT = """Summarize the conversation so far into a concise technical summary.
Include:
1. What task was being worked on
2. What approaches were tried
3. What files were modified and how
4. The current state of the changes
5. What verification failed and why

Keep it under 2000 tokens. Be precise and technical."""


class CompactAndRetry(RecoveryStrategy):
    """R2: Summarize context via LLM, include failure info, continue."""

    def __init__(self, llm_client: LLMClient | None = None):
        self._llm_client = llm_client

    @property
    def strategy_name(self) -> str:
        return "compact_and_retry"

    def set_llm_client(self, client: LLMClient) -> None:
        self._llm_client = client

    def recover(self, context: Context, verification: VerificationResult, task: Task) -> Context:
        if self._llm_client is None:
            # Fallback to R1 behavior if no LLM client
            feedback = (
                f"VERIFICATION FAILED. Please fix the issues and try again.\n\n"
                f"Failure details:\n{verification.message}"
            )
            context.add_user_message(feedback)
            context.recovery_count += 1
            context.is_complete = False
            return context

        # Generate summary of conversation
        summary_messages = list(context.messages) + [
            {"role": "user", "content": COMPACTION_PROMPT}
        ]
        response = self._llm_client.generate(messages=summary_messages, max_tokens=2048)
        summary = response.text_content

        # Track token cost
        context.token_usage.add(response.input_tokens, response.output_tokens)

        # Create compacted context
        from agent_verify.context import Context as ContextClass
        new_context = ContextClass(start_time=context.start_time)
        new_context.token_usage = context.token_usage
        new_context.tool_calls = context.tool_calls
        new_context.iteration_count = context.iteration_count
        new_context.verification_count = context.verification_count
        new_context.recovery_count = context.recovery_count + 1

        # Build compacted message
        compacted_content = (
            f"## Context Summary (from previous attempt)\n{summary}\n\n"
            f"## Verification Failure\n{verification.message}\n\n"
            f"## Task\n{task.description}\n\n"
            f"Please continue working on this task, addressing the verification failure above."
        )
        new_context.add_user_message(compacted_content)

        return new_context
