#!/usr/bin/env python3
"""BST (Binary Search over Trajectories) agent for SWE-bench.

Treats code generation as a search problem:
  1. Generate N full rollouts from root (with tqdm progress)
  2. Score each terminal with execution-based verifier
  3. Binary-search the best trajectory for the "critical bad decision"
  4. Re-expand from midpoint, compare scores, narrow range
  5. Pick best terminal → extract patch

Usage:
    uv run python scripts/bst_agent.py \
        --config configs/experiments/bst_test.yaml \
        --max-depth 100 --max-total-nodes 1500 \
        --rollouts-per-point 3 --parallel 1
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import builtins
_orig_print = builtins.print
print = functools.partial(_orig_print, flush=True)  # type: ignore

from tqdm import tqdm

from dotenv import load_dotenv
load_dotenv()

from agent_verify.benchmark.swebench import load_swebench_tasks, provision_workspace
from agent_verify.config import ExperimentConfig, load_config
from agent_verify.context import ToolCall
from agent_verify.harness import _create_llm_client, TASK_COMPLETE_MARKER
from agent_verify.llm.base import LLMClient
from agent_verify.logging.logger import ExperimentLogger
from agent_verify.tools import create_default_toolset

# Reuse from mcts_finegrained
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcts_finegrained import (
    ActionNode,
    ActionType,
    FGMCTSConfig,
    save_state,
    restore_state,
    get_diff,
    backpropagate,
    evaluate_terminal,
    evaluate_terminal_exec,
    reconstruct_messages,
    compact_path,
    serialize_tree,
    _append_jsonl,
    _strip_extra_tool_uses,
    _sibling_summary,
    COMPACTION_THRESHOLD,
    DIVERSITY_INJECT,
    READ_ONLY_TOOLS,
)


# ---------------------------------------------------------------------------
# BST Config
# ---------------------------------------------------------------------------
@dataclass
class BSTConfig:
    max_depth: int = 100
    max_total_nodes: int = 1500
    rollouts_per_point: int = 3
    early_stop_score: float = 1.0
    min_search_range: int = 5
    temperatures: list[float] = field(default_factory=lambda: [0.3, 0.6, 1.0])
    max_context: int = 131072
    compaction_threshold: float = COMPACTION_THRESHOLD
    test_timeout: int = 120
    max_children: int = 10
    ucb_c: float = 1.41
    diversity_injection: bool = True
    verifier_mode: str = "execution"
    verifier_version: str = "v2"
    breadth_weight: float = 0.0
    depth_penalty_weight: float = 0.0
    min_root_children: int = 3

    def to_fgmcts_config(self) -> FGMCTSConfig:
        return FGMCTSConfig(
            max_depth=self.max_depth,
            max_total_nodes=self.max_total_nodes,
            max_children=self.max_children,
            ucb_c=self.ucb_c,
            early_stop_score=self.early_stop_score,
            max_context=self.max_context,
            compaction_threshold=self.compaction_threshold,
            temperatures=self.temperatures,
            verifier_version=self.verifier_version,
            diversity_injection=self.diversity_injection,
            verifier_mode=self.verifier_mode,
            test_timeout=self.test_timeout,
            breadth_weight=self.breadth_weight,
            depth_penalty_weight=self.depth_penalty_weight,
            min_root_children=self.min_root_children,
        )


# ---------------------------------------------------------------------------
# expand_path with tqdm progress bar
# ---------------------------------------------------------------------------
def expand_path_tqdm(
    branch_node: ActionNode,
    task_msg: str,
    config: ExperimentConfig,
    llm: LLMClient,
    tools,
    tool_schemas: list[dict[str, Any]],
    workspace: str,
    cfg: FGMCTSConfig,
    trace_logger: ExperimentLogger,
    task_id: str,
    remaining_budget: int,
    label: str = "rollout",
    pbar_position: int = 0,
) -> tuple[ActionNode, int]:
    """Expand a full path from branch_node to terminal, with tqdm progress."""
    sibling_idx = len(branch_node.children)
    temps = cfg.temperatures
    temp = temps[min(sibling_idx, len(temps) - 1)]
    max_steps = min(cfg.max_depth - branch_node.depth, remaining_budget)

    # Restore git state
    restore_state(workspace, branch_node.effective_git_sha())

    current = branch_node
    nodes_created = 0

    # Diversity injection
    diversity_msg = ""
    if sibling_idx > 0 and cfg.diversity_injection and branch_node.children:
        diversity_msg = DIVERSITY_INJECT.format(
            sibling_summary=_sibling_summary(branch_node),
        )

    pbar = tqdm(
        total=max_steps, desc=f"  {label} (t={temp:.1f})",
        unit="step", position=pbar_position, leave=True,
        bar_format="{desc}: {bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
    )

    last_tool = ""
    for step in range(max_steps):
        if nodes_created >= remaining_budget:
            break

        # Reconstruct messages
        messages, effective_system = reconstruct_messages(
            current, task_msg, config.harness.system_prompt,
        )

        # Diversity injection on first step of alternative branch
        if step == 0 and diversity_msg:
            messages.append({"role": "user", "content": diversity_msg})

        # Check compaction
        if current.input_tokens > cfg.max_context * cfg.compaction_threshold and current.depth > 5:
            summary = compact_path(current, task_msg, llm)
            current.compaction_summary = summary
            current.compaction_count += 1
            pbar.set_postfix_str("compacted")
            messages, effective_system = reconstruct_messages(
                current, task_msg, config.harness.system_prompt,
            )

        # LLM call
        try:
            response = llm.generate(
                messages=messages,
                system=effective_system,
                tools=tool_schemas,
                max_tokens=config.harness.llm.max_tokens,
                temperature=temp,
            )
        except Exception as e:
            pbar.set_postfix_str(f"LLM error: {e!s:.40}")
            current.is_terminal = True
            break

        # Create new node
        new_node = ActionNode(
            parent=current,
            depth=current.depth + 1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            temperature=temp,
        )

        if response.has_tool_use:
            tu = response.tool_uses[0]
            new_node.action_type = ActionType.TOOL_CALL
            new_node.tool_name = tu["name"]
            new_node.tool_input = tu["input"]
            new_node.tool_use_id = tu["id"]
            new_node.assistant_content = _strip_extra_tool_uses(response.content)

            # Execute tool
            t_start = time.time()
            try:
                result = tools.execute(tu["name"], **tu["input"])
            except Exception as e:
                result = f"Error: {e}"
            new_node.tool_duration = time.time() - t_start
            new_node.tool_result = str(result)

            # Git state after write actions
            if new_node.is_write_action:
                new_node.git_sha = save_state(workspace, f"bst_{new_node.node_id}")

            last_tool = tu["name"]
            # Show tool call info in tqdm
            inp_short = json.dumps(tu["input"], default=str)[:60]
            pbar.set_postfix_str(f"{tu['name']}({inp_short})")

            trace_logger.log_tool_call(
                f"{task_id}_bst_{new_node.node_id}",
                ToolCall(tool_name=tu["name"], tool_input=tu["input"],
                         tool_result=str(result)[:5000], duration_seconds=new_node.tool_duration),
            )
        else:
            new_node.action_type = ActionType.TEXT_ONLY
            new_node.text_content = response.text_content
            new_node.assistant_content = response.content

            if TASK_COMPLETE_MARKER in response.text_content:
                new_node.is_terminal = True
                new_node.task_complete = True
                pbar.set_postfix_str("TASK_COMPLETE")

        trace_logger.log_llm_call(
            task_id=f"{task_id}_bst_{new_node.node_id}",
            iteration=new_node.depth,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            stop_reason=response.stop_reason,
            has_tool_use=response.has_tool_use,
            assistant_content=response.content,
        )

        current.children.append(new_node)
        nodes_created += 1
        current = new_node
        pbar.update(1)

        if new_node.is_terminal or new_node.depth >= cfg.max_depth:
            new_node.is_terminal = True
            break

        if not response.has_tool_use and response.stop_reason == "max_tokens":
            new_node.input_tokens = cfg.max_context

    current.is_terminal = True
    pbar.update(max_steps - pbar.n)  # fill remaining
    pbar.set_postfix_str(f"done d={current.depth} {'✓' if current.task_complete else '✗'}")
    pbar.close()
    return current, nodes_created


# ---------------------------------------------------------------------------
# BST solve for one task
# ---------------------------------------------------------------------------
def bst_solve_task(
    task,
    config: ExperimentConfig,
    output_dir: Path,
    bst_cfg: BSTConfig,
) -> dict[str, Any]:
    workspace = task.workspace_dir
    tag = f"[BST:{task.task_id}]"
    t0 = time.time()

    llm = _create_llm_client(config.harness.llm)
    tools = create_default_toolset(workspace)
    tool_schemas = tools.to_api_schemas()
    trace_logger = ExperimentLogger(config.experiment_id, output_dir=str(output_dir / "traces"))
    cfg = bst_cfg.to_fgmcts_config()

    trace_logger.log_run_start(
        task_id=task.task_id,
        config={"model": config.harness.llm.model, "bst": asdict(bst_cfg)},
        problem_statement=task.description,
    )

    base_sha = save_state(workspace, "bst_base")
    task_msg = (
        f"You are working in the repository at: {workspace}\n"
        f"Task ID: {task.task_id}\n\n"
        f"{task.description}"
    )

    root = ActionNode(
        node_id="root", action_type=ActionType.ROOT,
        depth=0, git_sha=base_sha,
    )

    total_nodes = 1
    terminals: list[ActionNode] = []
    early_stopped = False

    # ===================================================================
    # Phase 1: Initial rollouts from root
    # ===================================================================
    print(f"\n{'='*70}")
    print(f"{tag} Phase 1: {bst_cfg.rollouts_per_point} initial rollouts (max_depth={bst_cfg.max_depth})")
    print(f"{'='*70}")

    for i in range(bst_cfg.rollouts_per_point):
        remaining = bst_cfg.max_total_nodes - total_nodes
        if remaining <= 0:
            break

        terminal, created = expand_path_tqdm(
            branch_node=root,
            task_msg=task_msg,
            config=config,
            llm=llm,
            tools=tools,
            tool_schemas=tool_schemas,
            workspace=workspace,
            cfg=cfg,
            trace_logger=trace_logger,
            task_id=task.task_id,
            remaining_budget=remaining,
            label=f"R{i+1}/{bst_cfg.rollouts_per_point} from root",
        )
        total_nodes += created

        # Evaluate
        print(f"  Verifying rollout {i+1}...")
        score = evaluate_terminal(llm, terminal, task.description, workspace, base_sha, cfg=cfg)
        backpropagate(terminal, score)
        terminals.append(terminal)

        status = "COMPLETE" if terminal.task_complete else "max_depth"
        print(f"  ✓ Rollout {i+1}: depth={terminal.depth} status={status} "
              f"score={score:.2f} patch={len(terminal.patch)}c "
              f"[{total_nodes}/{bst_cfg.max_total_nodes} nodes]")

        if score >= bst_cfg.early_stop_score:
            print(f"  ★ Early stop! score={score:.2f} >= {bst_cfg.early_stop_score}")
            early_stopped = True
            break

    # ===================================================================
    # Phase 2: Binary search for critical bad decision
    # ===================================================================
    if not early_stopped:
        best_terminal = max(terminals, key=lambda t: t.verifier_score)
        best_score = best_terminal.verifier_score

        if best_score < bst_cfg.early_stop_score:
            search_path = best_terminal.path_from_root()
            lo, hi = 0, len(search_path) - 1
            bs_iteration = 0

            print(f"\n{'='*70}")
            print(f"{tag} Phase 2: Binary search (best_score={best_score:.2f}, "
                  f"trajectory_len={len(search_path)})")
            print(f"{'='*70}")

            while (hi - lo > bst_cfg.min_search_range
                   and total_nodes < bst_cfg.max_total_nodes):
                bs_iteration += 1
                mid = (lo + hi) // 2
                branch_node = search_path[mid]

                print(f"\n  ── BS iteration {bs_iteration}: "
                      f"range=[{lo},{hi}] mid={mid} "
                      f"node={branch_node.node_id} "
                      f"(tool={branch_node.tool_name or 'root'})")

                mid_scores = []
                for i in range(bst_cfg.rollouts_per_point):
                    remaining = bst_cfg.max_total_nodes - total_nodes
                    if remaining <= 0:
                        break

                    terminal, created = expand_path_tqdm(
                        branch_node=branch_node,
                        task_msg=task_msg,
                        config=config,
                        llm=llm,
                        tools=tools,
                        tool_schemas=tool_schemas,
                        workspace=workspace,
                        cfg=cfg,
                        trace_logger=trace_logger,
                        task_id=task.task_id,
                        remaining_budget=remaining,
                        label=f"BS{bs_iteration}.R{i+1} from d={mid}",
                    )
                    total_nodes += created

                    print(f"    Verifying BS{bs_iteration}.R{i+1}...")
                    score = evaluate_terminal(
                        llm, terminal, task.description, workspace, base_sha, cfg=cfg,
                    )
                    backpropagate(terminal, score)
                    terminals.append(terminal)
                    mid_scores.append(score)

                    print(f"    ✓ BS{bs_iteration}.R{i+1}: depth={terminal.depth} "
                          f"score={score:.2f} [{total_nodes}/{bst_cfg.max_total_nodes}]")

                    if score >= bst_cfg.early_stop_score:
                        early_stopped = True
                        break

                if early_stopped:
                    print(f"  ★ Early stop in BS! score={score:.2f}")
                    break

                avg_mid = sum(mid_scores) / len(mid_scores) if mid_scores else 0
                avg_orig = (branch_node.total_score / max(branch_node.visits, 1)
                            if branch_node.visits > 0 else 0)

                if avg_mid > avg_orig:
                    lo = mid
                    direction = "→ bad decision AFTER mid"
                else:
                    hi = mid
                    direction = "← bad decision BEFORE mid"

                print(f"  ── Result: avg_mid={avg_mid:.2f} vs avg_orig={avg_orig:.2f} "
                      f"{direction} → search [{lo},{hi}]")

                current_best = max(terminals, key=lambda t: t.verifier_score)
                if current_best.verifier_score > best_score:
                    best_score = current_best.verifier_score
                    print(f"  ★ New best score: {best_score:.2f}")

    # ===================================================================
    # Output
    # ===================================================================
    elapsed = time.time() - t0

    best = max(terminals, key=lambda n: n.verifier_score) if terminals else root
    if best.git_sha or best.parent:
        restore_state(workspace, best.effective_git_sha())
    final_patch = get_diff(workspace, base_sha) if terminals else ""

    patch_dir = output_dir / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    (patch_dir / f"{task.task_id}.diff").write_text(final_patch)

    tree_dir = output_dir / "trees"
    tree_dir.mkdir(parents=True, exist_ok=True)
    (tree_dir / f"{task.task_id}.json").write_text(
        json.dumps(serialize_tree(root), indent=2, default=str)
    )

    result = {
        "task_id": task.task_id,
        "total_nodes": total_nodes,
        "total_rollouts": len(terminals),
        "best_score": best.verifier_score if terminals else 0.0,
        "best_depth": best.depth if terminals else 0,
        "any_task_complete": any(t.task_complete for t in terminals),
        "patch_chars": len(final_patch),
        "wall_clock_seconds": elapsed,
        "terminal_scores": [round(t.verifier_score, 3) for t in terminals],
    }

    trace_logger.log_run_end(task.task_id, result)
    _append_jsonl(result, output_dir / "results.jsonl")

    has_diff = "yes" if final_patch.strip() else "no"
    print(f"\n{'='*70}")
    print(f"{tag} DONE")
    print(f"{'='*70}")
    print(f"  Rollouts: {len(terminals)}")
    print(f"  Nodes:    {total_nodes}/{bst_cfg.max_total_nodes}")
    print(f"  Best:     score={best.verifier_score:.2f} depth={best.depth}")
    print(f"  Patch:    {len(final_patch)} chars ({has_diff})")
    print(f"  Time:     {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  Scores:   {[round(t.verifier_score, 2) for t in terminals]}")

    return result


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------
async def run_experiment(
    config: ExperimentConfig,
    max_parallel: int,
    bst_cfg: BSTConfig,
) -> list[dict[str, Any]]:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {config.dataset_name} ({config.split})...")
    ids = config.instance_ids if config.instance_ids else None
    tasks = load_swebench_tasks(
        split=config.split, instance_ids=ids, dataset_name=config.dataset_name,
    )
    print(f"Loaded {len(tasks)} tasks")
    print(f"Model: {config.harness.llm.model}")
    print(f"BST config:")
    print(f"  max_depth={bst_cfg.max_depth}, max_nodes={bst_cfg.max_total_nodes}")
    print(f"  rollouts_per_point={bst_cfg.rollouts_per_point}, temps={bst_cfg.temperatures}")
    print(f"  early_stop={bst_cfg.early_stop_score}, min_search_range={bst_cfg.min_search_range}")
    print(f"  verifier_mode={bst_cfg.verifier_mode}")
    print(f"Parallel: {max_parallel}\n")

    print("Provisioning workspaces...")
    valid = []
    for t in tasks:
        try:
            provision_workspace(t, workspace_root=config.harness.workspace_dir)
            valid.append(t)
        except Exception as e:
            print(f"  SKIP: {t.task_id}: {e}")
    tasks = valid
    print(f"Ready ({len(tasks)} tasks).\n")

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futs = [
            loop.run_in_executor(pool, bst_solve_task, t, config, output_dir, bst_cfg)
            for t in tasks
        ]
        raw = await asyncio.gather(*futs, return_exceptions=True)

    results = []
    for t, r in zip(tasks, raw):
        if isinstance(r, Exception):
            print(f"  {t.task_id}: EXCEPTION: {r}")
            results.append({"task_id": t.task_id, "error": str(r)})
        else:
            results.append(r)

    total = len(results)
    has_patch = sum(1 for r in results if r.get("patch_chars", 0) > 0)
    any_complete = sum(1 for r in results if r.get("any_task_complete", False))

    summary = {
        "experiment_id": config.experiment_id,
        "model": config.harness.llm.model,
        "bst_config": asdict(bst_cfg),
        "tasks": total,
        "has_patch": has_patch,
        "any_task_complete": any_complete,
        "per_task": results,
    }
    spath = output_dir / f"{config.experiment_id}_summary.json"
    spath.write_text(json.dumps(summary, indent=2, default=str))

    print(f"\n{'='*60}")
    print(f"BST Agent Summary — {config.experiment_id}")
    print(f"{'='*60}")
    print(f"Tasks: {total}, Has patch: {has_patch}, Agent completed: {any_complete}")
    for r in results:
        tid = r.get("task_id", "?")
        sc = r.get("best_score", 0)
        nr = r.get("total_rollouts", 0)
        nn = r.get("total_nodes", 0)
        print(f"  {tid}: score={sc:.2f}, rollouts={nr}, nodes={nn}")
    print(f"Saved to {spath}")
    print(f"\nDocker eval:")
    print(f"  uv run python scripts/docker_eval.py "
          f"--patch-dir {output_dir}/patches "
          f"--run-name {config.experiment_id} "
          f"--dataset {config.dataset_name} --split {config.split} "
          f"--report-dir {output_dir}/docker_eval --max-workers 10")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="BST (Binary Search over Trajectories) agent")
    p.add_argument("--config", required=True)
    p.add_argument("--max-depth", type=int, default=100)
    p.add_argument("--max-total-nodes", type=int, default=1500)
    p.add_argument("--rollouts-per-point", type=int, default=3)
    p.add_argument("--early-stop-score", type=float, default=1.0)
    p.add_argument("--min-search-range", type=int, default=5)
    p.add_argument("--max-context", type=int, default=131072)
    p.add_argument("--temperatures", type=str, default="0.3,0.6,1.0")
    p.add_argument("--parallel", type=int, default=1)
    p.add_argument("--verifier-mode", type=str, default="execution",
                   choices=["execution", "llm"])
    p.add_argument("--test-timeout", type=int, default=120)
    p.add_argument("--no-diversity", action="store_true")
    args = p.parse_args()

    bst_cfg = BSTConfig(
        max_depth=args.max_depth,
        max_total_nodes=args.max_total_nodes,
        rollouts_per_point=args.rollouts_per_point,
        early_stop_score=args.early_stop_score,
        min_search_range=args.min_search_range,
        max_context=args.max_context,
        temperatures=[float(x) for x in args.temperatures.split(",")],
        test_timeout=args.test_timeout,
        verifier_mode=args.verifier_mode,
        diversity_injection=not args.no_diversity,
    )

    config = load_config(args.config)
    asyncio.run(run_experiment(config, args.parallel, bst_cfg))


if __name__ == "__main__":
    main()
