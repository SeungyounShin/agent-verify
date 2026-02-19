"""V1: Self-review verification - LLM reviews its own output."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import VerificationResult, Verifier

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.llm.base import LLMClient


SELF_REVIEW_PROMPT = """Review the changes you have made so far for the following task.

## Task
{task_description}

## Your Changes
Review all the file modifications and tool outputs in the conversation above.

## Instructions
1. Check if the changes correctly address the task requirements.
2. Look for potential bugs, edge cases, or missing functionality.
3. Determine if the task is truly complete.

Respond with EXACTLY one of:
- "VERIFICATION_PASSED" if the changes are correct and complete
- "VERIFICATION_FAILED: <reason>" if there are issues

Be critical and thorough in your review."""


class SelfReviewVerifier(Verifier):
    """V1: Ask the LLM to review its own output."""

    @property
    def method_name(self) -> str:
        return "self_review"

    def verify(self, context: Context, task: Task, llm_client: LLMClient | None = None) -> VerificationResult:
        if llm_client is None:
            return VerificationResult(
                passed=False,
                message="Self-review requires an LLM client",
            )

        review_prompt = SELF_REVIEW_PROMPT.format(task_description=task.description)

        # Build messages: include conversation history + review request
        messages = list(context.messages) + [
            {"role": "user", "content": review_prompt}
        ]

        response = llm_client.generate(messages=messages, max_tokens=2048)
        text = response.text_content
        token_cost = response.input_tokens + response.output_tokens

        passed = "VERIFICATION_PASSED" in text
        return VerificationResult(
            passed=passed,
            message=text,
            details={"raw_response": text},
            token_cost=token_cost,
        )
