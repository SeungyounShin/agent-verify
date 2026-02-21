#!/usr/bin/env python3
"""CLI entry point for running experiments (async parallel execution)."""

from __future__ import annotations

import argparse
import asyncio
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
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


def _run_single(
    task: Task,
    config: ExperimentConfig,
    logger: ExperimentLogger,
    index: int,
    total: int,
) -> TaskResult:
    """Run a single task (called from thread pool)."""
    tag = f"[{index+1}/{total}] {task.task_id}"
    print(f"{tag}: Starting (repo: {task.repo})")

    # Provision workspace
    try:
        workspace = provision_workspace(
            task, workspace_root=config.harness.workspace_dir,
        )
        print(f"{tag}: Workspace ready")
    except Exception as e:
        print(f"{tag}: ERROR provisioning: {e}")
        return TaskResult(
            task_id=task.task_id,
            resolved=False,
            completion_reason="provision_error",
            error=str(e),
        )

    # Run agent
    try:
        harness = AgentHarness(config=config.harness, logger=logger)
        result = harness.run(task)
    except Exception as e:
        print(f"{tag}: ERROR in harness: {e}")
        traceback.print_exc()
        return TaskResult(
            task_id=task.task_id,
            resolved=False,
            completion_reason="harness_error",
            error=str(e),
        )

    # Print progress
    total_in = result.input_tokens + result.cache_creation_input_tokens + result.cache_read_input_tokens
    cache_pct = (result.cache_read_input_tokens / total_in * 100) if total_in else 0
    status = "AGENT_DONE" if result.completion_reason in ("verified", "agent_declared") else result.completion_reason
    print(f"{tag}: {status} | Tokens: {total_in + result.output_tokens:,} | "
          f"Cache: {cache_pct:.0f}% | Cost: ${result.cost_usd:.4f} | "
          f"Time: {result.wall_clock_seconds:.1f}s | Iters: {result.iterations}")

    return result


async def run_experiment_async(config: ExperimentConfig, max_parallel: int = 10) -> list[TaskResult]:
    """Run experiment with parallel task execution."""
    logger = ExperimentLogger(config.experiment_id, config.output_dir)

    # Load tasks
    if config.benchmark == "swebench":
        print("Loading SWE-bench Verified dataset...")
        instance_ids = config.instance_ids if config.instance_ids else None
        tasks = load_swebench_tasks(split="test", instance_ids=instance_ids)
        if not tasks:
            print("No tasks loaded.")
            return []
        print(f"Loaded {len(tasks)} tasks")
    else:
        print(f"Unknown benchmark: {config.benchmark}")
        return []

    all_results = []
    for trial in range(config.num_trials):
        print(f"\n{'='*60}")
        print(f"Trial {trial + 1}/{config.num_trials} — Running {len(tasks)} tasks "
              f"(max {max_parallel} parallel)")
        print(f"{'='*60}\n")

        loop = asyncio.get_event_loop()

        # Provision all workspaces first (sequential to avoid git conflicts)
        print("Provisioning all workspaces...")
        for task in tasks:
            try:
                provision_workspace(task, workspace_root=config.harness.workspace_dir)
            except Exception as e:
                print(f"  WARNING: {task.task_id} provision failed: {e}")
        print("All workspaces ready.\n")

        # Run agent harness on all tasks in parallel
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = []
            for i, task in enumerate(tasks):
                future = loop.run_in_executor(
                    executor,
                    _run_single,
                    task, config, logger, i, len(tasks),
                )
                futures.append(future)

            results = await asyncio.gather(*futures, return_exceptions=True)

        # Collect results
        task_results = []
        for i, (task, res) in enumerate(zip(tasks, results)):
            if isinstance(res, Exception):
                print(f"  {task.task_id}: EXCEPTION: {res}")
                task_results.append(TaskResult(
                    task_id=task.task_id,
                    resolved=False,
                    completion_reason="exception",
                    error=str(res),
                ))
            else:
                task_results.append(res)

        all_results.extend(task_results)

    # Save summary (no lightweight eval — use docker_eval.py separately)
    _save_summary(config, all_results)
    return all_results


def run_experiment(config: ExperimentConfig) -> list[TaskResult]:
    """Synchronous wrapper for backward compatibility."""
    return asyncio.run(run_experiment_async(config))


def _save_summary(config: ExperimentConfig, results: list[TaskResult]) -> None:
    summary_path = Path(config.output_dir) / f"{config.experiment_id}_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_count = sum(1 for r in results if r.resolved)
    total = len(results)
    total_cost = sum(r.cost_usd for r in results)
    total_tokens = sum(r.input_tokens + r.output_tokens for r in results)
    total_cache_read = sum(r.cache_read_input_tokens for r in results)
    total_all_input = sum(
        r.input_tokens + r.cache_creation_input_tokens + r.cache_read_input_tokens
        for r in results
    )
    cache_hit_rate = total_cache_read / total_all_input if total_all_input else 0

    summary = {
        "experiment_id": config.experiment_id,
        "config": config.model_dump(),
        "resolve_rate": resolved_count / total if total else 0,
        "resolved": resolved_count,
        "total": total,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 4),
        "cache_hit_rate": round(cache_hit_rate, 4),
        "avg_wall_clock_seconds": sum(r.wall_clock_seconds for r in results) / total if total else 0,
        "results": [
            {
                "task_id": r.task_id,
                "resolved": r.resolved,
                "tokens": r.input_tokens + r.output_tokens,
                "cache_read_tokens": r.cache_read_input_tokens,
                "cache_creation_tokens": r.cache_creation_input_tokens,
                "cost_usd": round(r.cost_usd, 4),
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
    print(f"Total cost: ${total_cost:.4f} | Cache hit rate: {cache_hit_rate:.1%}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run agent verification experiment")
    parser.add_argument("--config", required=True, help="Path to experiment YAML config")
    parser.add_argument("--task", help="Run a single ad-hoc task instead of benchmark")
    parser.add_argument("--parallel", type=int, default=10, help="Max parallel tasks")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.task:
        logger = ExperimentLogger(config.experiment_id, config.output_dir)
        harness = AgentHarness(config=config.harness, logger=logger)
        task = Task(
            task_id="adhoc_test",
            description=args.task,
            workspace_dir=config.harness.workspace_dir,
        )
        result = harness.run(task)
        print(f"\nResult: resolved={result.resolved}, "
              f"reason={result.completion_reason}, "
              f"tokens={result.input_tokens + result.output_tokens}")
    else:
        asyncio.run(run_experiment_async(config, max_parallel=args.parallel))


if __name__ == "__main__":
    main()
