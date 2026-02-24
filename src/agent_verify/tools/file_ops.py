"""File operation tools for the agent."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from typing import Any

from .base import Tool


class FileReadTool(Tool):
    """Read file contents with line numbers and windowed viewing."""

    def __init__(self, workspace_dir: str = "/tmp/agent-workspace"):
        self.workspace_dir = Path(workspace_dir)

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a file with line numbers. "
            "Returns up to 200 lines by default starting from line 1. "
            "Use offset and limit to navigate large files (e.g., offset=100, limit=200 "
            "shows lines 100-299). Lines over 2000 chars are truncated. "
            "Always read a file before editing it."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace root",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-indexed, default 0)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to return (default 200)",
                },
            },
            "required": ["path"],
        }

    def execute(self, *, path: str, offset: int = 0, limit: int = 200, **kwargs: Any) -> str:
        file_path = self.workspace_dir / path
        if not file_path.is_file():
            return f"Error: File not found: {path}"
        try:
            content = file_path.read_text()
            lines = content.splitlines()
            total = len(lines)

            start = max(0, offset)
            end = min(start + limit, total)

            numbered = []
            for i in range(start, end):
                line = lines[i]
                if len(line) > 2000:
                    line = line[:2000] + "... [truncated]"
                numbered.append(f"{i + 1:6d}\t{line}")

            result = f"[File: {path} ({total} lines total)]\n"
            if start > 0:
                result += f"... ({start} lines above)\n"
            result += "\n".join(numbered)
            if end < total:
                result += f"\n... ({total - end} lines below)"

            return result
        except Exception as e:
            return f"Error reading file: {e}"


class FileWriteTool(Tool):
    """Write content to a file."""

    def __init__(self, workspace_dir: str = "/tmp/agent-workspace"):
        self.workspace_dir = Path(workspace_dir)

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return (
            "Write content to a file at the given path. Creates parent directories if needed. "
            "This overwrites the entire file. For small changes, prefer file_edit instead."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace root",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        }

    def execute(self, *, path: str, content: str, **kwargs: Any) -> str:
        file_path = self.workspace_dir / path
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {e}"


class FileEditTool(Tool):
    """Edit a file by replacing a string, with optional lint check."""

    def __init__(self, workspace_dir: str = "/tmp/agent-workspace"):
        self.workspace_dir = Path(workspace_dir)
        self._has_flake8 = shutil.which("flake8") is not None

    @property
    def name(self) -> str:
        return "file_edit"

    @property
    def description(self) -> str:
        return (
            "Edit a file by replacing old_string with new_string. "
            "The old_string must appear exactly once in the file; if it appears "
            "multiple times, provide more surrounding context to make it unique. "
            "For Python files, the edit is automatically checked for syntax errors "
            "and rolled back if invalid. Always read the file first before editing."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace root",
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to find and replace",
                },
                "new_string": {
                    "type": "string",
                    "description": "The replacement string",
                },
            },
            "required": ["path", "old_string", "new_string"],
        }

    def _lint_check(self, file_path: Path) -> str | None:
        """Run flake8 fatal-error-only check. Returns error message or None."""
        if not self._has_flake8 or file_path.suffix != ".py":
            return None
        try:
            result = subprocess.run(
                ["flake8", "--select=E9,W6", "--isolated", "--no-cache", str(file_path)],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def execute(self, *, path: str, old_string: str, new_string: str, **kwargs: Any) -> str:
        file_path = self.workspace_dir / path
        if not file_path.is_file():
            return f"Error: File not found: {path}"
        try:
            content = file_path.read_text()
            if old_string not in content:
                return f"Error: old_string not found in {path}"
            count = content.count(old_string)
            if count > 1:
                return (
                    f"Error: old_string found {count} times in {path}. "
                    f"Provide more surrounding context to make it unique."
                )
            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content)

            # Lint check for Python files
            lint_error = self._lint_check(file_path)
            if lint_error:
                # Rollback
                file_path.write_text(content)
                return (
                    f"Edit rolled back — syntax error detected:\n{lint_error}\n"
                    f"Fix the syntax and try again."
                )

            return f"Successfully edited {path}"
        except Exception as e:
            return f"Error editing file: {e}"
