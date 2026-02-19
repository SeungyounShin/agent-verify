#!/usr/bin/env python3
"""Inspect a specific SWE-bench task."""

import json
from agent_verify.benchmark.swebench import load_swebench_tasks

TASK_ID = "sympy__sympy-22914"

tasks = load_swebench_tasks(instance_ids=[TASK_ID])
if not tasks:
    print(f"Task {TASK_ID} not found")
    exit(1)

task = tasks[0]
print(f"Task ID: {task.task_id}")
print(f"Repo: {task.repo}")
print(f"Base commit: {task.base_commit}")
print(f"Test command: {task.test_command}")
print(f"\n{'='*60}")
print(f"Problem Statement:\n{task.description}")
print(f"\n{'='*60}")
print(f"Gold Patch:\n{task.metadata['patch']}")
print(f"\n{'='*60}")
print(f"Test Patch:\n{task.metadata['test_patch']}")
print(f"\n{'='*60}")
print(f"FAIL_TO_PASS: {task.metadata['FAIL_TO_PASS']}")
print(f"Version: {task.metadata['version']}")
