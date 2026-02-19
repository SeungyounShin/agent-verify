"""SWE-bench lightweight task loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import Task


def load_swebench_tasks(
    dataset_path: str,
    instance_ids: list[str] | None = None,
) -> list[Task]:
    """Load SWE-bench tasks from a JSONL file.

    Args:
        dataset_path: Path to SWE-bench dataset (JSONL format).
        instance_ids: Optional list of specific instance IDs to load.
                      If None, loads all instances.

    Returns:
        List of Task objects.
    """
    tasks = []
    path = Path(dataset_path)

    if not path.exists():
        raise FileNotFoundError(f"SWE-bench dataset not found: {dataset_path}")

    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            instance_id = data.get("instance_id", "")

            if instance_ids and instance_id not in instance_ids:
                continue

            task = Task(
                task_id=instance_id,
                description=data.get("problem_statement", ""),
                repo=data.get("repo", ""),
                base_commit=data.get("base_commit", ""),
                test_command=_build_test_command(data),
                metadata={
                    "hints_text": data.get("hints_text", ""),
                    "patch": data.get("patch", ""),
                    "test_patch": data.get("test_patch", ""),
                    "version": data.get("version", ""),
                },
            )
            tasks.append(task)

    return tasks


def _build_test_command(data: dict[str, Any]) -> str:
    """Build a test command from SWE-bench task data."""
    # SWE-bench tasks typically have a test command in FAIL_TO_PASS or PASS_TO_PASS
    fail_to_pass = data.get("FAIL_TO_PASS", "")
    if isinstance(fail_to_pass, str) and fail_to_pass:
        try:
            test_ids = json.loads(fail_to_pass)
            if isinstance(test_ids, list) and test_ids:
                return f"python -m pytest {' '.join(test_ids)} -x --tb=short"
        except json.JSONDecodeError:
            pass
    return ""
