#!/usr/bin/env python3
"""Ralph Loop experiment: agent self-verifies with its own tests.

NO gold test leakage — the agent must write/run its own tests.
After each attempt, if the agent declared TASK_COMPLETE, we start a fresh
session telling it "a previous attempt was made but may be wrong, verify
more carefully and fix if needed."

The final evaluation uses Docker eval (offline) to measure actual resolve rate.
We run 10 tasks: 5 previously-failed + 5 previously-resolved from exp8.
This produces a confusion matrix comparing single-shot vs ralph-loop.

Usage:
    uv run python scripts/ralph_loop.py \
        --config configs/experiments/ralph_test.yaml \
        --max-iterations 3 --parallel 5
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import builtins
_orig_print = builtins.print
print = functools.partial(_orig_print, flush=True)  # type: ignore

from dotenv import load_dotenv
load_dotenv()

from agent_verify.benchmark.base import Task
from agent_verify.benchmark.swebench import load_swebench_tasks, provision_workspace
from agent_verify.config import ExperimentConfig, load_config
from agent_verify.context import Context, ToolCall
from agent_verify.harness import _create_llm_client, TASK_COMPLETE_MARKER
from agent_verify.logging.logger import ExperimentLogger
from agent_verify.tools import create_default_toolset

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
COMPACTION_THRESHOLD_RATIO = 0.75
DEFAULT_MAX_CONTEXT = 262144
DEFAULT_MAX_STEPS = 200

COMPACTION_PROMPT = """\
Your task is to create a detailed summary of the conversation so far, \
paying close attention to the user's explicit requests and your previous \
actions. This summary will be used as context when continuing the \
conversation, so preserve critical information including:
- What was accomplished
- Current work in progress
- Files involved
- Next steps
- Key user requests or constraints"""

COMPACTION_INJECT = """\

## Session Continuation (after context compaction #{n})

Your previous conversation was compacted because it exceeded the context \
window. The repository retains all your changes. Here is what you did so far:

{summary}

Continue working from where you left off. When done, say 'TASK_COMPLETE'.
"""

# The key ralph feedback — injected as user message after agent declares TASK_COMPLETE
RALPH_VERIFY_MSG = """\
Wait — before finishing, please verify your fix more carefully:

1. Write a small test script that reproduces the ORIGINAL bug (before your fix)
2. Run it to confirm your fix actually resolves the issue
3. Think about edge cases — does your fix handle all the cases mentioned in the issue?
4. Check if your change could break any existing functionality

If you find problems, fix them. If everything checks out, say 'TASK_COMPLETE' again."""

# For iteration >= 1: fresh session with summary of previous attempt
RALPH_RETRY_INJECT = """\

## Previous Attempt #{iteration} — Self-Verification

A previous agent attempted this task. Here is what it tried:

{attempt_summary}

The workspace has been completely reset to the original state.
Please attempt the fix again. This time:
1. Carefully read the issue and understand the root cause
2. Make the minimal fix
3. Write a test script to verify your fix works
4. Run the test to confirm
5. Say 'TASK_COMPLETE' when done and verified
"""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@dataclass
class IterationResult:
    task_id: str
    iteration: int
    completion_reason: str
    steps: int
    input_tokens: int
    output_tokens: int
    wall_clock_seconds: float
    had_self_verify: bool  # did the agent go through verify loop?


@dataclass
class TaskResult:
    task_id: str
    total_iterations: int
    final_completion_reason: str
    total_input_tokens: int
    total_output_tokens: int
    total_wall_clock_seconds: float
    iterations: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log_lock = threading.Lock()


def _append_jsonl(data: dict, path: Path) -> None:
    with _log_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(data, default=str) + "\n")


# ---------------------------------------------------------------------------
# Transcript builder
# ---------------------------------------------------------------------------
def _messages_to_transcript(messages: list[dict[str, Any]], max_chars: int = 8000) -> str:
    lines = []
    for msg in messages:
        role = msg.get("role", "?").upper()
        content = msg.get("content", "")
        if isinstance(content, str):
            lines.append(f"[{role}] {content[:2000]}")
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    lines.append(f"[{role}] {str(block)[:500]}")
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    lines.append(f"[{role}] {block['text'][:2000]}")
                elif btype == "tool_use":
                    inp = json.dumps(block.get("input", {}), default=str)[:500]
                    lines.append(f"[TOOL_CALL] {block['name']}({inp})")
    text = "\n".join(lines)
    return text[:max_chars] + ("\n...[truncated]" if len(text) > max_chars else "")


# ---------------------------------------------------------------------------
# Single agent attempt
# ---------------------------------------------------------------------------
def _run_agent_attempt(
    task: Task,
    config: ExperimentConfig,
    system_prompt: str,
    max_context: int,
    trace_logger: ExperimentLogger,
    iteration: int,
    max_steps: int = 200,
) -> tuple[str, int, int, int, list[dict]]:
    """Run one agent attempt with self-verification loop.

    Returns (completion_reason, steps, input_tokens, output_tokens, messages).
    """
    tag = f"[{task.task_id}][iter={iteration}]"
    llm = _create_llm_client(config.harness.llm)
    tools = create_default_toolset(task.workspace_dir)
    tool_schemas = tools.to_api_schemas()

    total_in = 0
    total_out = 0
    steps = 0
    last_input_tokens = 0
    completion_reason = ""
    compactions = 0
    task_complete_count = 0  # track how many times agent said TASK_COMPLETE

    task_msg = (
        f"You are working in the repository at: {task.workspace_dir}\n"
        f"Task ID: {task.task_id}\n\n"
        f"{task.description}"
    )

    current_system = system_prompt
    ctx = Context()
    ctx.add_user_message(task_msg)

    for step in range(max_steps):
        # Auto-compaction
        if step > 0 and last_input_tokens > max_context * COMPACTION_THRESHOLD_RATIO:
            print(f"{tag} Compacting (input_tokens={last_input_tokens})")
            transcript = _messages_to_transcript(ctx.messages)
            try:
                resp = llm.generate(
                    messages=[{"role": "user",
                               "content": f"{COMPACTION_PROMPT}\n\n## Conversation:\n{transcript}"}],
                    system="You are a technical summarizer.",
                    max_tokens=2048, temperature=0.3,
                )
                summary = resp.text_content
                total_in += resp.input_tokens
                total_out += resp.output_tokens
            except Exception as e:
                print(f"{tag} Compaction failed: {e}")
                summary = transcript[:4000]

            compactions += 1
            current_system = system_prompt + COMPACTION_INJECT.format(
                n=compactions, summary=summary,
            )
            ctx = Context()
            ctx.add_user_message(task_msg)
            last_input_tokens = 0

        # LLM call
        try:
            response = llm.generate(
                messages=ctx.messages,
                system=current_system,
                tools=tool_schemas,
                max_tokens=config.harness.llm.max_tokens,
                temperature=config.harness.llm.temperature,
            )
        except Exception as e:
            print(f"{tag} LLM error at step {step}: {e}")
            completion_reason = "llm_error"
            break

        last_input_tokens = response.input_tokens
        total_in += response.input_tokens
        total_out += response.output_tokens
        steps += 1

        tool_names = [tu["name"] for tu in response.tool_uses] if response.has_tool_use else []
        print(f"{tag} step={step} in={response.input_tokens} out={response.output_tokens} "
              f"tools={tool_names} stop={response.stop_reason}")

        trace_logger.log_llm_call(
            task_id=task.task_id, iteration=step,
            input_tokens=response.input_tokens, output_tokens=response.output_tokens,
            stop_reason=response.stop_reason, has_tool_use=response.has_tool_use,
            assistant_content=response.content,
        )

        ctx.add_assistant_message(response.content)

        if response.has_tool_use:
            for tu in response.tool_uses:
                t_start = time.time()
                try:
                    result = tools.execute(tu["name"], **tu["input"])
                except Exception as e:
                    result = f"Error: {e}"
                t_dur = time.time() - t_start
                trace_logger.log_tool_call(task.task_id, ToolCall(
                    tool_name=tu["name"], tool_input=tu["input"],
                    tool_result=str(result), duration_seconds=t_dur,
                ))
                ctx.add_tool_result(tu["id"], result)
        else:
            if TASK_COMPLETE_MARKER in response.text_content:
                task_complete_count += 1

                if task_complete_count == 1:
                    # First TASK_COMPLETE — inject self-verification prompt
                    print(f"{tag} First TASK_COMPLETE at step {step}, injecting verify prompt")
                    ctx.add_user_message(RALPH_VERIFY_MSG)
                    # Continue the loop — agent will verify and say TASK_COMPLETE again
                else:
                    # Second TASK_COMPLETE — agent verified, done
                    completion_reason = "agent_declared_verified"
                    print(f"{tag} Verified TASK_COMPLETE at step {step}")
                    break
            elif response.stop_reason == "end_turn":
                ctx.add_user_message(
                    "Continue working on the task. "
                    "When done, include 'TASK_COMPLETE' in your response."
                )
            elif response.stop_reason == "max_tokens":
                last_input_tokens = max_context
    else:
        completion_reason = "max_steps"

    return completion_reason, steps, total_in, total_out, ctx.messages


# ---------------------------------------------------------------------------
# Ralph Loop for a single task
# ---------------------------------------------------------------------------
def ralph_loop_task(
    task: Task,
    config: ExperimentConfig,
    output_dir: Path,
    max_iterations: int,
    max_context: int,
    max_steps: int = 200,
) -> TaskResult:
    tag = f"[{task.task_id}]"
    t0 = time.time()
    log_path = output_dir / f"{config.experiment_id}_ralph_log.jsonl"

    trace_logger = ExperimentLogger(config.experiment_id, output_dir=str(output_dir))
    trace_logger.log_run_start(
        task_id=task.task_id,
        config={
            "llm": {"provider": config.harness.llm.provider, "model": config.harness.llm.model,
                     "max_tokens": config.harness.llm.max_tokens, "temperature": config.harness.llm.temperature},
            "max_context": max_context, "max_steps": max_steps,
            "max_ralph_iterations": max_iterations,
            "system_prompt": config.harness.system_prompt,
        },
        problem_statement=task.description,
    )

    llm = _create_llm_client(config.harness.llm)
    base_prompt = config.harness.system_prompt

    total_in = 0
    total_out = 0
    iteration_results = []
    prev_summary = ""

    for iteration in range(max_iterations):
        iter_t0 = time.time()
        print(f"\n{'='*60}")
        print(f"{tag} RALPH ITERATION {iteration + 1}/{max_iterations}")
        print(f"{'='*60}")

        # 1. Reset workspace
        subprocess.run(
            ["git", "checkout", "--force", "HEAD"],
            cwd=task.workspace_dir, capture_output=True, timeout=30,
        )
        subprocess.run(
            ["git", "clean", "-fdx"],
            cwd=task.workspace_dir, capture_output=True, timeout=30,
        )

        # 2. Build system prompt
        if iteration == 0:
            system_prompt = base_prompt
        else:
            system_prompt = base_prompt + RALPH_RETRY_INJECT.format(
                iteration=iteration,
                attempt_summary=prev_summary,
            )

        # 3. Run agent with self-verification
        completion_reason, steps, in_tok, out_tok, messages = _run_agent_attempt(
            task, config, system_prompt, max_context, trace_logger, iteration,
            max_steps=max_steps,
        )
        total_in += in_tok
        total_out += out_tok

        # 4. Save patch
        diff = subprocess.run(
            ["git", "diff", "HEAD"], cwd=task.workspace_dir,
            capture_output=True, text=True, timeout=30,
        ).stdout
        patch_dir = output_dir / "patches" / f"iter_{iteration}"
        patch_dir.mkdir(parents=True, exist_ok=True)
        (patch_dir / f"{task.task_id}.diff").write_text(diff)

        iter_elapsed = time.time() - iter_t0
        had_verify = "verified" in completion_reason

        iter_result = IterationResult(
            task_id=task.task_id, iteration=iteration,
            completion_reason=completion_reason, steps=steps,
            input_tokens=in_tok, output_tokens=out_tok,
            wall_clock_seconds=iter_elapsed,
            had_self_verify=had_verify,
        )
        iteration_results.append(asdict(iter_result))
        _append_jsonl(asdict(iter_result), log_path)

        has_diff = "yes" if diff.strip() else "no"
        print(f"{tag} iter={iteration} reason={completion_reason} "
              f"steps={steps} diff={has_diff} time={iter_elapsed:.0f}s")

        # 5. If agent verified, done with this task (no more iterations)
        if had_verify:
            print(f"{tag} Agent self-verified, moving on.")
            break

        # 6. Generate summary for next iteration
        if iteration < max_iterations - 1:
            transcript = _messages_to_transcript(messages, max_chars=6000)
            try:
                fb_resp = llm.generate(
                    messages=[{"role": "user", "content": (
                        f"Summarize what this agent attempted for the following task.\n\n"
                        f"## Task:\n{task.description[:2000]}\n\n"
                        f"## Agent Conversation:\n{transcript}\n\n"
                        f"Provide: (1) what was changed, (2) files modified, "
                        f"(3) any test results the agent observed. Be concise (under 300 words)."
                    )}],
                    system="You are a technical summarizer.",
                    max_tokens=1024, temperature=0.3,
                )
                prev_summary = fb_resp.text_content
                total_in += fb_resp.input_tokens
                total_out += fb_resp.output_tokens
            except Exception as e:
                print(f"{tag} Summary generation failed: {e}")
                prev_summary = transcript[:3000]

    elapsed = time.time() - t0
    final_reason = iteration_results[-1]["completion_reason"] if iteration_results else "none"

    result = TaskResult(
        task_id=task.task_id,
        total_iterations=len(iteration_results),
        final_completion_reason=final_reason,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_wall_clock_seconds=elapsed,
        iterations=iteration_results,
    )

    trace_logger.log_run_end(task.task_id, {
        "total_iterations": len(iteration_results),
        "final_completion_reason": final_reason,
        "total_wall_clock_seconds": elapsed,
    })

    print(f"\n{tag} Final: {final_reason} | {len(iteration_results)} iterations | {elapsed:.0f}s")
    return result


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------
async def run_experiment(
    config: ExperimentConfig,
    max_parallel: int,
    max_iterations: int,
    max_context: int,
    max_steps: int = 200,
) -> list[TaskResult]:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {config.dataset_name} ({config.split})...")
    ids = config.instance_ids if config.instance_ids else None
    tasks = load_swebench_tasks(
        split=config.split, instance_ids=ids, dataset_name=config.dataset_name,
    )
    print(f"Loaded {len(tasks)} tasks")
    print(f"Settings: max_steps={max_steps}, max_iterations={max_iterations}, "
          f"max_parallel={max_parallel}\n")

    print("Provisioning workspaces...")
    for t in tasks:
        try:
            provision_workspace(t, workspace_root=config.harness.workspace_dir)
        except Exception as e:
            print(f"  WARN: {t.task_id}: {e}")
    print("Ready.\n")

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futs = [
            loop.run_in_executor(
                pool, ralph_loop_task, t, config, output_dir,
                max_iterations, max_context, max_steps,
            )
            for t in tasks
        ]
        raw = await asyncio.gather(*futs, return_exceptions=True)

    results = []
    for t, r in zip(tasks, raw):
        if isinstance(r, Exception):
            print(f"  {t.task_id}: EXCEPTION: {r}")
            results.append(TaskResult(
                task_id=t.task_id, total_iterations=0,
                final_completion_reason="exception",
                total_input_tokens=0, total_output_tokens=0,
                total_wall_clock_seconds=0,
            ))
        else:
            results.append(r)

    # Summary
    print(f"\n{'='*60}")
    print(f"RALPH LOOP SUMMARY")
    print(f"{'='*60}")
    for r in results:
        verified = "verified" in r.final_completion_reason
        print(f"  {r.task_id:45s} iters={r.total_iterations} "
              f"reason={r.final_completion_reason:25s} time={r.total_wall_clock_seconds:.0f}s "
              f"{'SELF-VERIFIED' if verified else ''}")

    summary = {
        "experiment_id": config.experiment_id,
        "mode": "ralph_loop",
        "max_iterations": max_iterations,
        "max_steps": max_steps,
        "tasks": len(results),
        "per_task": [asdict(r) for r in results],
    }
    spath = output_dir / f"{config.experiment_id}_ralph_summary.json"
    spath.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved to {spath}")
    print(f"\nNext: run Docker eval on final patches to get actual resolve rate:")
    print(f"  uv run python scripts/docker_eval.py "
          f"--patch-dir {output_dir}/patches/iter_0 "  # or last iter per task
          f"--run-name {config.experiment_id}_ralph "
          f"--dataset {config.dataset_name} --split {config.split}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Ralph Loop experiment")
    p.add_argument("--config", required=True)
    p.add_argument("--max-iterations", type=int, default=3,
                   help="Max Ralph loop iterations per task")
    p.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                   help="Max LLM steps per iteration")
    p.add_argument("--parallel", type=int, default=5)
    p.add_argument("--max-context", type=int, default=DEFAULT_MAX_CONTEXT)
    args = p.parse_args()

    config = load_config(args.config)
    asyncio.run(run_experiment(
        config, args.parallel, args.max_iterations, args.max_context, args.max_steps,
    ))


if __name__ == "__main__":
    main()
