"""Main agent harness with pluggable verification and recovery."""

from __future__ import annotations

import time
from typing import Any

from agent_verify.benchmark.base import Task, TaskResult
from agent_verify.config import (
    HarnessConfig,
    LLMConfig,
    VerificationGranularity,
)
from agent_verify.context import Context, ToolCall
from agent_verify.llm.base import LLMClient, LLMResponse
from agent_verify.logging.logger import ExperimentLogger
from agent_verify.recovery import create_recovery_strategy
from agent_verify.recovery.base import RecoveryStrategy
from agent_verify.recovery.compact import CompactAndRetry
from agent_verify.tools import create_default_toolset
from agent_verify.tools.base import ToolSet
from agent_verify.verification import create_verifier
from agent_verify.verification.base import Verifier

TASK_COMPLETE_MARKER = "TASK_COMPLETE"


class AgentHarness:
    """Main agent loop with pluggable verification and recovery."""

    def __init__(
        self,
        config: HarnessConfig,
        logger: ExperimentLogger | None = None,
    ):
        self.config = config
        self.llm_client: LLMClient = _create_llm_client(config.llm)
        self.tools: ToolSet = create_default_toolset(config.workspace_dir)
        self.verifier: Verifier = create_verifier(config.verification_method)
        self.recovery: RecoveryStrategy = create_recovery_strategy(config.recovery_strategy)
        self.logger = logger

        # Inject LLM client into recovery strategy if needed
        if isinstance(self.recovery, CompactAndRetry):
            self.recovery.set_llm_client(self.llm_client)

    def run(self, task: Task) -> TaskResult:
        """Run the agent on a task with verification/recovery loop."""
        task.workspace_dir = task.workspace_dir or self.config.workspace_dir

        if self.logger:
            self.logger.log_run_start(task.task_id, self.config.model_dump())

        context = Context()
        context.add_user_message(task.description)
        recovery_attempts = 0

        try:
            result = self._agent_loop(context, task, recovery_attempts)
        except Exception as e:
            result = TaskResult(
                task_id=task.task_id,
                resolved=False,
                input_tokens=context.token_usage.input_tokens,
                output_tokens=context.token_usage.output_tokens,
                wall_clock_seconds=context.elapsed_seconds,
                tool_call_count=len(context.tool_calls),
                verification_count=context.verification_count,
                recovery_count=context.recovery_count,
                iterations=context.iteration_count,
                completion_reason="error",
                error=str(e),
            )

        if self.logger:
            self.logger.log_run_end(task.task_id, {
                "resolved": result.resolved,
                "completion_reason": result.completion_reason,
                "tokens": result.input_tokens + result.output_tokens,
                "wall_clock_seconds": result.wall_clock_seconds,
                "cost_usd": context.token_usage.total_cost_usd,
                "cache_hit_rate": context.token_usage.cache_hit_rate,
            })

        return result

    def _agent_loop(self, context: Context, task: Task, recovery_attempts: int) -> TaskResult:
        """Core agent loop: generate -> execute -> verify -> recover."""
        while not context.is_complete:
            # Guard: max iterations
            if context.iteration_count >= self.config.max_iterations:
                context.is_complete = True
                context.completion_reason = "max_iterations"
                break

            # Guard: token budget
            if context.token_usage.total >= self.config.max_tokens_budget:
                context.is_complete = True
                context.completion_reason = "token_budget"
                break

            # Guard: timeout
            if context.elapsed_seconds >= self.config.timeout_seconds:
                context.is_complete = True
                context.completion_reason = "timeout"
                break

            # Generate LLM response
            response = self.llm_client.generate(
                messages=context.messages,
                system=self.config.system_prompt,
                tools=self.tools.to_api_schemas(),
                max_tokens=self.config.llm.max_tokens,
                temperature=self.config.llm.temperature,
            )

            # Track tokens + cost
            context.token_usage.add(
                response.input_tokens, response.output_tokens,
                cache_creation_input_tokens=response.cache_creation_input_tokens,
                cache_read_input_tokens=response.cache_read_input_tokens,
                cost_usd=response.cost_usd,
            )
            context.iteration_count += 1

            if self.logger:
                self.logger.log_llm_call(
                    task.task_id,
                    context.iteration_count,
                    response.input_tokens,
                    response.output_tokens,
                    response.stop_reason,
                    response.has_tool_use,
                    cache_creation_input_tokens=response.cache_creation_input_tokens,
                    cache_read_input_tokens=response.cache_read_input_tokens,
                    cost_usd=response.cost_usd,
                )

            # Add assistant response to context
            context.add_assistant_message(response.content)

            # Process tool calls
            if response.has_tool_use:
                for tool_use in response.tool_uses:
                    tool_result = self._execute_tool(tool_use, task, context)
                    context.add_tool_result(tool_use["id"], tool_result)

                    # Per-step verification (G3)
                    if self.config.verification_granularity == VerificationGranularity.PER_STEP:
                        should_continue = self._run_verification(context, task, recovery_attempts)
                        if not should_continue:
                            return self._build_result(context, task)
            else:
                # No tool use — check if agent declares completion
                if TASK_COMPLETE_MARKER in response.text_content:
                    context.is_complete = True
                    context.completion_reason = "agent_declared"

                    # Task-end verification (G1 and G2 both verify at end)
                    should_continue = self._run_verification(context, task, recovery_attempts)
                    if not should_continue:
                        return self._build_result(context, task)
                elif response.stop_reason == "end_turn":
                    # Agent stopped without tool use or completion marker
                    # Nudge it to continue or declare completion
                    context.add_user_message(
                        "Please continue working on the task. "
                        "When done, include 'TASK_COMPLETE' in your response."
                    )

        return self._build_result(context, task)

    def _execute_tool(self, tool_use: dict[str, Any], task: Task, context: Context) -> str:
        """Execute a single tool call and track it."""
        start = time.time()
        try:
            result = self.tools.execute(tool_use["name"], **tool_use["input"])
        except Exception as e:
            result = f"Error: {e}"
        duration = time.time() - start

        tc = ToolCall(
            tool_name=tool_use["name"],
            tool_input=tool_use["input"],
            tool_result=result[:5000],
            duration_seconds=duration,
        )
        context.record_tool_call(tc)

        if self.logger:
            self.logger.log_tool_call(task.task_id, tc)

        return result

    def _run_verification(self, context: Context, task: Task, recovery_attempts: int) -> bool:
        """Run verification. Returns True if loop should continue, False if done.

        Returns False when:
        - Verification passed (task complete)
        - Max recovery attempts exceeded
        """
        verification = self.verifier.verify(context, task, self.llm_client)
        context.verification_count += 1

        if self.logger:
            self.logger.log_verification(
                task.task_id, verification, self.verifier.method_name,
            )

        if verification.passed:
            context.is_complete = True
            context.completion_reason = "verified"
            return False  # Done — stop loop

        # Verification failed — attempt recovery
        if recovery_attempts >= self.config.max_recovery_attempts:
            context.is_complete = True
            context.completion_reason = "max_recovery"
            return False

        if self.logger:
            self.logger.log_recovery(
                task.task_id,
                self.recovery.strategy_name,
                recovery_attempts + 1,
            )

        # Recovery modifies context (or creates new one)
        new_context = self.recovery.recover(context, verification, task)

        # For fresh restart (R3), we get a new context — recurse
        if new_context is not context:
            result = self._agent_loop(new_context, task, recovery_attempts + 1)
            # Copy result back to original context for final reporting
            context.is_complete = True
            context.completion_reason = new_context.completion_reason or result.completion_reason
            context.token_usage = new_context.token_usage
            context.verification_count = new_context.verification_count
            context.recovery_count = new_context.recovery_count
            return False
        else:
            # R1: same context, continue loop
            context.is_complete = False
            return True

    def _build_result(self, context: Context, task: Task) -> TaskResult:
        """Build final result from context."""
        resolved = context.completion_reason == "verified"
        return TaskResult(
            task_id=task.task_id,
            resolved=resolved,
            input_tokens=context.token_usage.input_tokens,
            output_tokens=context.token_usage.output_tokens,
            cache_creation_input_tokens=context.token_usage.cache_creation_input_tokens,
            cache_read_input_tokens=context.token_usage.cache_read_input_tokens,
            cost_usd=context.token_usage.total_cost_usd,
            wall_clock_seconds=context.elapsed_seconds,
            tool_call_count=len(context.tool_calls),
            verification_count=context.verification_count,
            recovery_count=context.recovery_count,
            iterations=context.iteration_count,
            completion_reason=context.completion_reason,
        )


def _create_llm_client(llm_config: LLMConfig) -> LLMClient:
    """Create LLM client based on provider config."""
    provider = llm_config.provider

    if provider == "anthropic":
        from agent_verify.llm.anthropic import AnthropicClient
        return AnthropicClient(model=llm_config.model)

    if provider in ("openai", "vllm", "local"):
        from agent_verify.llm.openai_compat import OpenAICompatClient
        return OpenAICompatClient(
            model=llm_config.model,
            base_url=llm_config.base_url or "http://localhost:8000/v1",
            api_key=llm_config.api_key or "dummy",
        )

    raise ValueError(f"Unknown LLM provider: {provider}")
