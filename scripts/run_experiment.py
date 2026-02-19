#!/usr/bin/env python3
"""CLI entry point for running experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_verify.benchmark.base import Task, TaskResult
from agent_verify.benchmark.swebench import load_swebench_tasks
from agent_verify.config import ExperimentConfig, load_config
from agent_verify.harness import AgentHarness
from agent_verify.logging.logger import ExperimentLogger


def run_experiment(config: ExperimentConfig) -> list[TaskResult]:
    """Run a full experiment."""
    logger = ExperimentLogger(config.experiment_id, config.output_dir)

    # Load tasks
    if config.benchmark == "swebench":
        if not config.instance_ids:
            print("Warning: No instance_ids specified. Provide a dataset path and IDs.")
            return []
        # TODO: Support dataset path in config
        tasks: list[Task] = []
    else:
        print(f"Unknown benchmark: {config.benchmark}")
        return []

    harness = AgentHarness(config=config.harness, logger=logger)

    results = []
    for trial in range(config.num_trials):
        print(f"\n=== Trial {trial + 1}/{config.num_trials} ===")
        for task in tasks:
            print(f"  Running task: {task.task_id}")
            result = harness.run(task)
            results.append(result)
            print(f"    Resolved: {result.resolved} | "
                  f"Tokens: {result.input_tokens + result.output_tokens} | "
                  f"Time: {result.wall_clock_seconds:.1f}s")

    # Save summary
    summary_path = Path(config.output_dir) / f"{config.experiment_id}_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "experiment_id": config.experiment_id,
        "config": config.model_dump(),
        "results": [
            {
                "task_id": r.task_id,
                "resolved": r.resolved,
                "tokens": r.input_tokens + r.output_tokens,
                "wall_clock_seconds": r.wall_clock_seconds,
                "tool_calls": r.tool_call_count,
                "verifications": r.verification_count,
                "recoveries": r.recovery_count,
                "iterations": r.iterations,
                "completion_reason": r.completion_reason,
            }
            for r in results
        ],
        "resolve_rate": sum(1 for r in results if r.resolved) / len(results) if results else 0,
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nSummary saved to {summary_path}")

    return results


def run_single_task(config: ExperimentConfig, task_description: str) -> TaskResult:
    """Run a single ad-hoc task (for testing/development)."""
    logger = ExperimentLogger(config.experiment_id, config.output_dir)
    harness = AgentHarness(config=config.harness, logger=logger)

    task = Task(
        task_id="adhoc_test",
        description=task_description,
        workspace_dir=config.harness.workspace_dir,
    )

    return harness.run(task)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run agent verification experiment")
    parser.add_argument("--config", required=True, help="Path to experiment YAML config")
    parser.add_argument("--task", help="Run a single ad-hoc task instead of benchmark")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.task:
        result = run_single_task(config, args.task)
        print(f"\nResult: resolved={result.resolved}, "
              f"reason={result.completion_reason}, "
              f"tokens={result.input_tokens + result.output_tokens}")
    else:
        run_experiment(config)


if __name__ == "__main__":
    main()
