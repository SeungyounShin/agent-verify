"""Grep tool for the agent — wraps ripgrep for fast code search."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from .base import Tool


class GrepTool(Tool):
    """Search file contents using ripgrep."""

    def __init__(self, workspace_dir: str = "/tmp/agent-workspace"):
        self.workspace_dir = workspace_dir
        self._rg = shutil.which("rg") or "rg"

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return (
            "Search file contents for a regex pattern using ripgrep. "
            "Returns matching lines with file paths and line numbers. "
            "Use this instead of `bash grep/rg` for searching code. "
            "Supports full regex syntax. Use glob_filter to restrict to specific "
            "file types (e.g., '*.py'). Results are capped at max_results (default 50)."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in (relative to workspace, default '.')",
                },
                "glob_filter": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py', '*.js')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matching lines to return (default 50)",
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines before and after each match (default 0)",
                },
            },
            "required": ["pattern"],
        }

    def execute(
        self,
        *,
        pattern: str,
        path: str = ".",
        glob_filter: str | None = None,
        max_results: int = 50,
        context_lines: int = 0,
        **kwargs: Any,
    ) -> str:
        cmd = [self._rg, "--no-heading", "--line-number", "--color=never"]

        if context_lines > 0:
            cmd += [f"-C{context_lines}"]

        if glob_filter:
            cmd += ["--glob", glob_filter]

        # Cap results to avoid huge output
        cmd += ["--max-count", str(max_results * 2)]  # oversample, trim later

        cmd += [pattern, path]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 1:
                return "No matches found."
            if result.returncode not in (0, 1):
                err = result.stderr.strip()
                return f"Error running ripgrep: {err}" if err else "Error running ripgrep."

            lines = result.stdout.splitlines()
            total = len(lines)
            if total > max_results:
                lines = lines[:max_results]
                output = "\n".join(lines)
                output += f"\n... ({total - max_results} more matches, increase max_results to see)"
            else:
                output = "\n".join(lines)

            return output if output.strip() else "No matches found."

        except FileNotFoundError:
            return (
                "Error: ripgrep (rg) not found. "
                "Use `bash` tool with `grep -rn` as fallback."
            )
        except subprocess.TimeoutExpired:
            return "Error: Search timed out after 30 seconds. Try a more specific pattern or path."
        except Exception as e:
            return f"Error: {e}"
