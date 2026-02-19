"""V3: Spec comparison verification - LLM compares output against task spec."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import VerificationResult, Verifier

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.llm.base import LLMClient


SPEC_COMPARISON_PROMPT = """You are a verification agent. Compare the work done in the conversation above against the original task specification below.

## Original Task Specification
{task_description}

## Instructions
1. Carefully compare every requirement in the spec against the actual changes made.
2. Check for completeness: are all requirements addressed?
3. Check for correctness: do the changes actually fulfill each requirement?
4. Check for regressions: could the changes break existing functionality?

Respond with EXACTLY one of:
- "VERIFICATION_PASSED" if all requirements are met
- "VERIFICATION_FAILED: <specific list of unmet requirements or issues>"

Be strict and thorough. Only pass if ALL requirements are clearly met."""


class SpecComparisonVerifier(Verifier):
    """V3: Use a separate LLM call to compare output against task spec."""

    @property
    def method_name(self) -> str:
        return "spec_comparison"

    def verify(self, context: Context, task: Task, llm_client: LLMClient | None = None) -> VerificationResult:
        if llm_client is None:
            return VerificationResult(
                passed=False,
                message="Spec comparison requires an LLM client",
            )

        prompt = SPEC_COMPARISON_PROMPT.format(task_description=task.description)

        messages = list(context.messages) + [
            {"role": "user", "content": prompt}
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
