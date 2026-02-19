"""File operation tools for the agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Tool


class FileReadTool(Tool):
    """Read file contents."""

    def __init__(self, workspace_dir: str = "/tmp/agent-workspace"):
        self.workspace_dir = Path(workspace_dir)

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to workspace root",
                },
            },
            "required": ["path"],
        }

    def execute(self, *, path: str, **kwargs: Any) -> str:
        file_path = self.workspace_dir / path
        if not file_path.is_file():
            return f"Error: File not found: {path}"
        try:
            content = file_path.read_text()
            return content
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
        return "Write content to a file at the given path. Creates parent directories if needed."

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
    """Edit a file by replacing a string."""

    def __init__(self, workspace_dir: str = "/tmp/agent-workspace"):
        self.workspace_dir = Path(workspace_dir)

    @property
    def name(self) -> str:
        return "file_edit"

    @property
    def description(self) -> str:
        return "Edit a file by replacing old_string with new_string."

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
                return f"Error: old_string found {count} times in {path}. Provide more context to make it unique."
            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content)
            return f"Successfully edited {path}"
        except Exception as e:
            return f"Error editing file: {e}"
