"""SWE-bench dataset loader and workspace provisioner."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from datasets import load_dataset

from .base import Task


def load_swebench_tasks(
    split: str = "test",
    instance_ids: list[str] | None = None,
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
) -> list[Task]:
    """Load SWE-bench tasks from HuggingFace datasets.

    Args:
        split: Dataset split ("test", "train", etc.).
        instance_ids: Optional list of specific instance IDs to load.
        dataset_name: HuggingFace dataset name.

    Returns:
        List of Task objects.
    """
    ds = load_dataset(dataset_name, split=split)

    tasks = []
    for row in ds:
        instance_id = row.get("instance_id", "")

        if instance_ids and instance_id not in instance_ids:
            continue

        task = Task(
            task_id=instance_id,
            description=row.get("problem_statement", ""),
            repo=row.get("repo", ""),
            base_commit=row.get("base_commit", ""),
            test_command=_build_test_command(row),
            metadata={
                "hints_text": row.get("hints_text", ""),
                "patch": row.get("patch", ""),
                "test_patch": row.get("test_patch", ""),
                "version": row.get("version", ""),
                "FAIL_TO_PASS": row.get("FAIL_TO_PASS", ""),
                "PASS_TO_PASS": row.get("PASS_TO_PASS", ""),
                "environment_setup_commit": row.get("environment_setup_commit", ""),
            },
        )
        tasks.append(task)

    return tasks


def provision_workspace(task: Task, workspace_root: str = "/tmp/agent-workspace") -> str:
    """Clone repo and checkout base commit for a SWE-bench task.

    Args:
        task: The SWE-bench task.
        workspace_root: Root directory for workspaces.

    Returns:
        Path to the provisioned workspace directory.
    """
    workspace = Path(workspace_root) / task.task_id.replace("/", "__")

    if workspace.exists():
        # Already provisioned — reset to base commit
        subprocess.run(
            ["git", "checkout", task.base_commit, "--force"],
            cwd=workspace, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "clean", "-fdx"],
            cwd=workspace, capture_output=True, check=True,
        )
        task.workspace_dir = str(workspace)
        return str(workspace)

    workspace.parent.mkdir(parents=True, exist_ok=True)

    # Clone the repo
    repo_url = f"https://github.com/{task.repo}.git"
    subprocess.run(
        ["git", "clone", "--depth", "50", repo_url, str(workspace)],
        capture_output=True, check=True, timeout=300,
    )

    # Fetch the specific commit if shallow clone doesn't have it
    try:
        subprocess.run(
            ["git", "cat-file", "-e", task.base_commit],
            cwd=workspace, capture_output=True, check=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["git", "fetch", "--unshallow"],
            cwd=workspace, capture_output=True, timeout=600,
        )

    # Checkout base commit
    subprocess.run(
        ["git", "checkout", task.base_commit],
        cwd=workspace, capture_output=True, check=True,
    )

    task.workspace_dir = str(workspace)
    return str(workspace)


def apply_test_patch(task: Task) -> bool:
    """Apply the test patch from SWE-bench (adds the failing tests).

    Returns True if patch applied successfully.
    """
    test_patch = task.metadata.get("test_patch", "")
    if not test_patch or not task.workspace_dir:
        return False

    try:
        result = subprocess.run(
            ["git", "apply", "--check", "-"],
            input=test_patch, text=True,
            cwd=task.workspace_dir,
            capture_output=True,
        )
        if result.returncode != 0:
            # Patch may already be applied or conflict
            return False

        subprocess.run(
            ["git", "apply", "-"],
            input=test_patch, text=True,
            cwd=task.workspace_dir,
            capture_output=True, check=True,
        )
        return True
    except Exception:
        return False


def evaluate_task(task: Task) -> dict[str, Any]:
    """Evaluate whether the agent's changes pass the SWE-bench tests.

    This applies the test patch (if not already applied) and runs the
    FAIL_TO_PASS tests to check if the agent resolved the issue.

    Returns:
        Dict with evaluation results.
    """
    if not task.workspace_dir:
        return {"resolved": False, "error": "No workspace directory"}

    # Apply test patch to add the failing tests
    apply_test_patch(task)

    # Build evaluation command from test patch file paths + test function names
    test_cmd = _build_eval_command(task)
    if not test_cmd:
        return {"resolved": False, "error": "No test command could be constructed"}

    # Use clean env to avoid uv venv interference and cross-workspace
    # pollution (e.g., pytest-dev workspace interfering with other tasks).
    import os
    clean_env = {k: v for k, v in os.environ.items()
                 if k not in ("VIRTUAL_ENV", "PYTHONPATH")}
    clean_env["PATH"] = ":".join(
        p for p in os.environ.get("PATH", "").split(":")
        if ".venv" not in p
    )
    # Ensure PYTHONDONTWRITEBYTECODE to avoid __pycache__ interference
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"

    try:
        result = subprocess.run(
            ["bash", "-c", test_cmd],
            cwd=task.workspace_dir,
            capture_output=True, text=True,
            timeout=300,
            env=clean_env,
        )
        resolved = result.returncode == 0
        return {
            "resolved": resolved,
            "exit_code": result.returncode,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-3000:] if result.stderr else "",
            "test_command": test_cmd,
        }
    except subprocess.TimeoutExpired:
        return {"resolved": False, "error": "Test execution timed out"}
    except Exception as e:
        return {"resolved": False, "error": str(e)}


def _build_eval_command(task: Task) -> str:
    """Build the evaluation test command by resolving test IDs to file paths.

    SWE-bench FAIL_TO_PASS contains test function names like 'test_Foo'.
    We need to find the actual test file that contains these functions
    and build a proper pytest command.
    """
    fail_to_pass = task.metadata.get("FAIL_TO_PASS", "")
    if not fail_to_pass:
        return ""

    try:
        test_ids = json.loads(fail_to_pass) if isinstance(fail_to_pass, str) else fail_to_pass
    except json.JSONDecodeError:
        return ""

    if not isinstance(test_ids, list) or not test_ids:
        return ""

    # Try to extract test file paths from the test patch
    test_patch = task.metadata.get("test_patch", "")
    test_files = _extract_files_from_patch(test_patch)

    if test_files:
        # Build pytest node IDs: file::function
        pytest_args = []
        for test_id in test_ids:
            # test_id might already be a full path like "tests/test_foo.py::test_bar"
            if "::" in test_id or "/" in test_id:
                pytest_args.append(test_id)
            else:
                # Match function name to test files
                for tf in test_files:
                    pytest_args.append(f"{tf}::{test_id}")
                    break  # Use first matching file
        quoted = ' '.join(shlex.quote(a) for a in pytest_args)
        return f"python3 -m pytest {quoted} -x --tb=short"

    # Fallback: try using test IDs directly (might work if they're already paths)
    quoted = ' '.join(shlex.quote(a) for a in test_ids)
    return f"python3 -m pytest {quoted} -x --tb=short"


def _extract_files_from_patch(patch: str) -> list[str]:
    """Extract file paths from a git diff patch."""
    files = []
    for line in patch.split("\n"):
        if line.startswith("+++ b/"):
            filepath = line[6:]
            files.append(filepath)
    return files


def _build_test_command(data: dict[str, Any]) -> str:
    """Build a test command from SWE-bench task data for agent use.

    This generates a command the agent can use during its run.
    """
    fail_to_pass = data.get("FAIL_TO_PASS", "")
    if isinstance(fail_to_pass, str) and fail_to_pass:
        try:
            test_ids = json.loads(fail_to_pass)
            if isinstance(test_ids, list) and test_ids:
                # Extract test files from test_patch for better paths
                test_patch = data.get("test_patch", "")
                test_files = _extract_files_from_patch(test_patch)
                if test_files:
                    pytest_args = []
                    for test_id in test_ids:
                        if "::" in test_id or "/" in test_id:
                            pytest_args.append(test_id)
                        else:
                            for tf in test_files:
                                pytest_args.append(f"{tf}::{test_id}")
                                break
                    quoted = ' '.join(shlex.quote(a) for a in pytest_args)
                    return f"python3 -m pytest {quoted} -x --tb=short"
                quoted = ' '.join(shlex.quote(a) for a in test_ids)
                return f"python3 -m pytest {quoted} -x --tb=short"
        except json.JSONDecodeError:
            pass
    return ""
