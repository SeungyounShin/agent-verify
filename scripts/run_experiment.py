#!/usr/bin/env python3
"""CLI entry point for running experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from agent_verify.benchmark.base import Task, TaskResult
from agent_verify.benchmark.swebench import (
    evaluate_task,
    load_swebench_tasks,
    provision_workspace,
)
from agent_verify.config import ExperimentConfig, load_config
from agent_verify.harness import AgentHarness
from agent_verify.logging.logger import ExperimentLogger


def run_experiment(config: ExperimentConfig) -> list[TaskResult]:
    """Run a full experiment on SWE-bench tasks."""
    logger = ExperimentLogger(config.experiment_id, config.output_dir)

    # Load tasks
    if config.benchmark == "swebench":
        print("Loading SWE-bench Verified dataset...")
        instance_ids = config.instance_ids if config.instance_ids else None
        tasks = load_swebench_tasks(
            split="test",
            instance_ids=instance_ids,
        )
        if not tasks:
            print("No tasks loaded. Check instance_ids in config.")
            return []
        print(f"Loaded {len(tasks)} tasks")
    else:
        print(f"Unknown benchmark: {config.benchmark}")
        return []

    results = []
    for trial in range(config.num_trials):
        print(f"\n{'='*60}")
        print(f"Trial {trial + 1}/{config.num_trials}")
        print(f"{'='*60}")

        for i, task in enumerate(tasks):
            print(f"\n[{i+1}/{len(tasks)}] Task: {task.task_id}")
            print(f"  Repo: {task.repo}")

            # Provision workspace (clone repo, checkout base commit)
            try:
                print(f"  Provisioning workspace...")
                workspace = provision_workspace(
                    task,
                    workspace_root=config.harness.workspace_dir,
                )
                print(f"  Workspace: {workspace}")
            except Exception as e:
                print(f"  ERROR provisioning workspace: {e}")
                results.append(TaskResult(
                    task_id=task.task_id,
                    resolved=False,
                    completion_reason="provision_error",
                    error=str(e),
                ))
                continue

            # Run the agent
            harness = AgentHarness(config=config.harness, logger=logger)
            result = harness.run(task)

            # Evaluate with SWE-bench test suite
            print(f"  Evaluating...")
            eval_result = evaluate_task(task)
            result.resolved = eval_result.get("resolved", False)
            result.metadata["eval"] = eval_result

            results.append(result)
            status = "RESOLVED" if result.resolved else "FAILED"
            print(f"  {status} | Tokens: {result.input_tokens + result.output_tokens:,} | "
                  f"Time: {result.wall_clock_seconds:.1f}s | "
                  f"Iterations: {result.iterations}")

    # Save summary
    _save_summary(config, results)
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


def _save_summary(config: ExperimentConfig, results: list[TaskResult]) -> None:
    summary_path = Path(config.output_dir) / f"{config.experiment_id}_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_count = sum(1 for r in results if r.resolved)
    total = len(results)
    summary = {
        "experiment_id": config.experiment_id,
        "config": config.model_dump(),
        "resolve_rate": resolved_count / total if total else 0,
        "resolved": resolved_count,
        "total": total,
        "total_tokens": sum(r.input_tokens + r.output_tokens for r in results),
        "avg_wall_clock_seconds": sum(r.wall_clock_seconds for r in results) / total if total else 0,
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
                "error": r.error,
            }
            for r in results
        ],
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nSummary saved to {summary_path}")
    print(f"Resolve rate: {resolved_count}/{total} ({summary['resolve_rate']:.1%})")


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
