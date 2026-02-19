"""V4: E2E verification - external tool-based end-to-end verification."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from .base import VerificationResult, Verifier

if TYPE_CHECKING:
    from agent_verify.benchmark.base import Task
    from agent_verify.context import Context
    from agent_verify.llm.base import LLMClient


class E2EVerifier(Verifier):
    """V4: External tool-based end-to-end verification.

    Runs a task-specific E2E verification script (e.g., Playwright, Puppeteer).
    This is a skeleton for Phase 0 — full implementation depends on benchmark.
    """

    def __init__(self, timeout: int = 300):
        self.timeout = timeout

    @property
    def method_name(self) -> str:
        return "e2e"

    def verify(self, context: Context, task: Task, llm_client: LLMClient | None = None) -> VerificationResult:
        e2e_command = task.metadata.get("e2e_command")
        if not e2e_command:
            return VerificationResult(
                passed=False,
                message="No E2E verification command specified for this task",
            )

        try:
            result = subprocess.run(
                ["bash", "-c", e2e_command],
                cwd=task.workspace_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            passed = result.returncode == 0
            output = (result.stdout or "") + (result.stderr or "")
            if len(output) > 10000:
                output = output[:5000] + "\n...[truncated]...\n" + output[-5000:]

            return VerificationResult(
                passed=passed,
                message=f"E2E verification {'passed' if passed else 'failed'}",
                details={
                    "exit_code": result.returncode,
                    "output": output,
                    "e2e_command": e2e_command,
                },
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                message=f"E2E verification timed out after {self.timeout}s",
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                message=f"E2E verification error: {e}",
            )
