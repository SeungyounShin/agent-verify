"""Base benchmark and task data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    """A single benchmark task for the agent to solve."""
    task_id: str
    description: str
    repo: str = ""
    base_commit: str = ""
    test_command: str = ""
    workspace_dir: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of running an agent on a single task."""
    task_id: str
    resolved: bool
    input_tokens: int = 0
    output_tokens: int = 0
    wall_clock_seconds: float = 0.0
    tool_call_count: int = 0
    verification_count: int = 0
    recovery_count: int = 0
    iterations: int = 0
    completion_reason: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
