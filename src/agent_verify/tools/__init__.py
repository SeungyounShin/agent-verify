"""Agent tools."""

from .base import Tool, ToolSet
from .bash import BashTool
from .file_ops import FileEditTool, FileReadTool, FileWriteTool


def create_default_toolset(workspace_dir: str = "/tmp/agent-workspace") -> ToolSet:
    """Create the default set of tools for the agent."""
    return ToolSet([
        FileReadTool(workspace_dir),
        FileWriteTool(workspace_dir),
        FileEditTool(workspace_dir),
        BashTool(workspace_dir),
    ])
