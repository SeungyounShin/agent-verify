"""V2: Test execution verification - run existing test suite."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

from .base import VerificationResult, Verifier

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.llm.base import LLMClient


class TestExecutionVerifier(Verifier):
    """V2: Run the existing test suite to verify changes."""

    def __init__(self, timeout: int = 300):
        self.timeout = timeout

    @property
    def method_name(self) -> str:
        return "test_execution"

    def verify(self, context: Context, task: Task, llm_client: LLMClient | None = None) -> VerificationResult:
        test_command = task.test_command
        if not test_command:
            return VerificationResult(
                passed=False,
                message="No test command specified for this task",
            )

        workspace = task.workspace_dir
        try:
            result = subprocess.run(
                ["bash", "-c", test_command],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += ("\n" if output else "") + result.stderr

            # Truncate very long output
            if len(output) > 10000:
                output = output[:5000] + "\n...[truncated]...\n" + output[-5000:]

            passed = result.returncode == 0
            return VerificationResult(
                passed=passed,
                message=f"Tests {'passed' if passed else 'failed'} (exit code {result.returncode})",
                details={
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:5000] if result.stdout else "",
                    "stderr": result.stderr[:5000] if result.stderr else "",
                    "test_command": test_command,
                },
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                message=f"Tests timed out after {self.timeout}s",
                details={"test_command": test_command, "timeout": self.timeout},
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                message=f"Error running tests: {e}",
                details={"error": str(e)},
            )
