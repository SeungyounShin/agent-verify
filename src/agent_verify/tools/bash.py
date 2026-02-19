"""Bash execution tool for the agent."""

from __future__ import annotations

import subprocess
from typing import Any

from .base import Tool


class BashTool(Tool):
    """Execute bash commands in the workspace."""

    def __init__(self, workspace_dir: str = "/tmp/agent-workspace", timeout: int = 120):
        self.workspace_dir = workspace_dir
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return (
            "Execute a bash command in the workspace directory. "
            "Use this for running tests, installing packages, git operations, etc."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                },
            },
            "required": ["command"],
        }

    def execute(self, *, command: str, **kwargs: Any) -> str:
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += ("\n" if output else "") + result.stderr
            if result.returncode != 0:
                output += f"\n[Exit code: {result.returncode}]"
            return output if output else "[No output]"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {self.timeout} seconds"
        except Exception as e:
            return f"Error executing command: {e}"
