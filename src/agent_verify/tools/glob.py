"""Glob tool for the agent — find files by name pattern."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Tool


class GlobTool(Tool):
    """Find files matching a glob pattern."""

    def __init__(self, workspace_dir: str = "/tmp/agent-workspace"):
        self.workspace_dir = Path(workspace_dir)

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return (
            "Find files matching a glob pattern (e.g., '**/*.py', 'src/**/*.js'). "
            "Returns file paths relative to the search directory, sorted alphabetically. "
            "Use this instead of `bash find/ls` for locating files. "
            "Results are capped at 200 files."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '**/*.py', 'tests/**/test_*.py')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (relative to workspace, default '.')",
                },
            },
            "required": ["pattern"],
        }

    def execute(self, *, pattern: str, path: str = ".", **kwargs: Any) -> str:
        search_dir = self.workspace_dir / path
        if not search_dir.is_dir():
            return f"Error: Directory not found: {path}"

        try:
            matches = sorted(search_dir.glob(pattern))
            # Filter to files only
            files = [m for m in matches if m.is_file()]

            if not files:
                return "No files found matching the pattern."

            total = len(files)
            cap = 200
            result_files = files[:cap]

            lines = []
            for f in result_files:
                try:
                    rel = f.relative_to(self.workspace_dir)
                except ValueError:
                    rel = f
                lines.append(str(rel))

            output = "\n".join(lines)
            if total > cap:
                output += f"\n... ({total - cap} more files, refine pattern to narrow results)"
            else:
                output = f"[{total} files found]\n" + output

            return output

        except Exception as e:
            return f"Error: {e}"
