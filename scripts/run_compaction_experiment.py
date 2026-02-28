#!/usr/bin/env python3
"""Auto-compaction experiment: agent runs with unlimited budget.

V0 baseline fails many tasks because it hits max_iterations or token_budget.
This experiment removes those limits. Instead, when the conversation's input
tokens approach the vLLM max_model_len, we auto-compact the conversation
(LLM-generated summary) and continue in a fresh context — repo state preserved.

Agent declares TASK_COMPLETE → save patch → done.
No retry on Docker eval failure. Docker eval runs after all tasks finish.

Compare: V0 (4/23 = 17.4%) vs auto-compaction (?/23).
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
from agent_verify.llm.base import LLMClient
from agent_verify.logging.logger import ExperimentLogger
from agent_verify.tools import create_default_toolset

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
COMPACTION_THRESHOLD_RATIO = 0.75  # compact when input_tokens > 75% of max_context
DEFAULT_MAX_CONTEXT = 131072       # vLLM max_model_len
DEFAULT_MAX_STEPS = 200            # absolute safety cap on LLM calls per task

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


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@dataclass
class TaskRunResult:
    task_id: str
    completed: bool          # agent said TASK_COMPLETE
    completion_reason: str   # agent_declared, timeout, max_steps, llm_error
    compactions: int
    total_steps: int         # LLM calls
    total_input_tokens: int
    total_output_tokens: int
    wall_clock_seconds: float


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
# Transcript builder for compaction
# ---------------------------------------------------------------------------
def _messages_to_transcript(messages: list[dict[str, Any]], max_chars: int = 12000) -> str:
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
                elif btype == "tool_result":
                    lines.append(f"[TOOL_RESULT] {str(block.get('content', ''))[:1000]}")
                # skip _reasoning

    text = "\n".join(lines)
    return text[:max_chars] + ("\n...[truncated]" if len(text) > max_chars else "")


# ---------------------------------------------------------------------------
# Core: agent loop with auto-compaction
# ---------------------------------------------------------------------------
def run_task(
    task: Task,
    config: ExperimentConfig,
    output_dir: Path,
    max_context: int,
    max_steps: int = 200,
) -> TaskRunResult:
    tag = f"[{task.task_id}]"
    t0 = time.time()
    log_path = output_dir / f"{config.experiment_id}_log.jsonl"
    print(f"{tag} Starting task (max_context={max_context}, max_steps={max_steps})", flush=True)

    # Structured trace logger (writes full conversation to JSONL)
    trace_logger = ExperimentLogger(config.experiment_id, output_dir=str(output_dir))
    trace_logger.log_run_start(
        task_id=task.task_id,
        config={
            "llm": {"provider": config.harness.llm.provider, "model": config.harness.llm.model,
                     "max_tokens": config.harness.llm.max_tokens, "temperature": config.harness.llm.temperature},
            "max_context": max_context, "max_steps": max_steps,
            "system_prompt": config.harness.system_prompt,
        },
        problem_statement=task.description,
    )

    llm = _create_llm_client(config.harness.llm)
    tools = create_default_toolset(task.workspace_dir)
    tool_schemas = tools.to_api_schemas()
    base_prompt = config.harness.system_prompt

    total_in = 0
    total_out = 0
    compactions = 0
    steps = 0
    last_input_tokens = 0
    completion_reason = ""

    # Build task message with workspace context
    task_msg = (
        f"You are working in the repository at: {task.workspace_dir}\n"
        f"Task ID: {task.task_id}\n\n"
        f"{task.description}"
    )

    # Current system prompt (may grow with compaction summaries)
    system_prompt = base_prompt

    # Fresh context
    ctx = Context()
    ctx.add_user_message(task_msg)

    for step in range(max_steps):
        # --- Auto-compaction ---
        if step > 0 and last_input_tokens > max_context * COMPACTION_THRESHOLD_RATIO:
            print(f"{tag} Compacting (input_tokens={last_input_tokens}, "
                  f"threshold={int(max_context * COMPACTION_THRESHOLD_RATIO)})")
            transcript = _messages_to_transcript(ctx.messages)
            try:
                resp = llm.generate(
                    messages=[{"role": "user",
                               "content": f"{COMPACTION_PROMPT}\n\n## Conversation:\n{transcript}"}],
                    system="You are a technical summarizer.",
                    max_tokens=2048,
                    temperature=0.3,
                )
                summary = resp.text_content
                total_in += resp.input_tokens
                total_out += resp.output_tokens
            except Exception as e:
                print(f"{tag} Compaction LLM failed: {e}, using raw truncation")
                summary = transcript[:4000]

            compactions += 1
            system_prompt = base_prompt + COMPACTION_INJECT.format(
                n=compactions, summary=summary,
            )
            ctx = Context()
            ctx.add_user_message(task_msg)
            last_input_tokens = 0  # reset after compaction
            print(f"{tag} Compaction #{compactions} done ({len(summary)} chars)")

        # --- LLM call ---
        try:
            response = llm.generate(
                messages=ctx.messages,
                system=system_prompt,
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

        # --- Tool calls ---
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
            # --- Check TASK_COMPLETE ---
            if TASK_COMPLETE_MARKER in response.text_content:
                completion_reason = "agent_declared"
                print(f"{tag} TASK_COMPLETE at step {step}")
                break
            elif response.stop_reason == "end_turn":
                ctx.add_user_message(
                    "Continue working on the task. "
                    "When done, include 'TASK_COMPLETE' in your response."
                )
            elif response.stop_reason == "max_tokens":
                # Output truncated — force compaction next step
                last_input_tokens = max_context
    else:
        completion_reason = "max_steps"

    elapsed = time.time() - t0

    # Save patch
    diff = subprocess.run(
        ["git", "diff", "HEAD"], cwd=task.workspace_dir,
        capture_output=True, text=True, timeout=30,
    ).stdout
    patch_dir = output_dir / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    (patch_dir / f"{task.task_id}.diff").write_text(diff)

    result = TaskRunResult(
        task_id=task.task_id,
        completed=completion_reason == "agent_declared",
        completion_reason=completion_reason,
        compactions=compactions,
        total_steps=steps,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        wall_clock_seconds=elapsed,
    )
    trace_logger.log_run_end(task.task_id, {
        "resolved": completion_reason == "agent_declared",
        "completion_reason": completion_reason,
        "compactions": compactions, "total_steps": steps,
        "total_input_tokens": total_in, "total_output_tokens": total_out,
        "wall_clock_seconds": elapsed,
    })
    _append_jsonl(asdict(result), log_path)

    has_diff = "yes" if diff.strip() else "no"
    print(f"{tag} Done: {completion_reason} | steps={steps} compactions={compactions} "
          f"tokens={total_in + total_out:,} time={elapsed:.0f}s diff={has_diff}")

    return result


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------
async def run_experiment(
    config: ExperimentConfig,
    max_parallel: int,
    max_context: int,
    max_steps: int = 200,
) -> list[TaskRunResult]:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {config.dataset_name} ({config.split})...")
    ids = config.instance_ids if config.instance_ids else None
    tasks = load_swebench_tasks(
        split=config.split, instance_ids=ids, dataset_name=config.dataset_name,
    )
    print(f"Loaded {len(tasks)} tasks")
    print(f"Settings: max_steps={max_steps}, max_context={max_context}, parallel={max_parallel}\n")

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
            loop.run_in_executor(pool, run_task, t, config, output_dir, max_context, max_steps)
            for t in tasks
        ]
        raw = await asyncio.gather(*futs, return_exceptions=True)

    results = []
    for t, r in zip(tasks, raw):
        if isinstance(r, Exception):
            print(f"  {t.task_id}: EXCEPTION: {r}")
            results.append(TaskRunResult(
                task_id=t.task_id, completed=False, completion_reason="exception",
                compactions=0, total_steps=0, total_input_tokens=0,
                total_output_tokens=0, wall_clock_seconds=0,
            ))
        else:
            results.append(r)

    # Summary
    completed = sum(1 for r in results if r.completed)
    total_tok = sum(r.total_input_tokens + r.total_output_tokens for r in results)
    total_comp = sum(r.compactions for r in results)
    summary = {
        "experiment_id": config.experiment_id,
        "tasks": len(results),
        "agent_completed": completed,
        "total_tokens": total_tok,
        "total_compactions": total_comp,
        "per_task": [asdict(r) for r in results],
    }
    spath = output_dir / f"{config.experiment_id}_summary.json"
    spath.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSummary: {completed}/{len(results)} agent-completed, "
          f"{total_comp} compactions, {total_tok:,} tokens")
    print(f"Saved to {spath}")
    print(f"\nRun Docker eval separately:")
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
    p = argparse.ArgumentParser(description="Auto-compaction experiment")
    p.add_argument("--config", required=True)
    p.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                   help="Max LLM steps per task")
    p.add_argument("--parallel", type=int, default=5)
    p.add_argument("--max-context", type=int, default=DEFAULT_MAX_CONTEXT)
    args = p.parse_args()

    config = load_config(args.config)
    asyncio.run(run_experiment(config, args.parallel, args.max_context, args.max_steps))


if __name__ == "__main__":
    main()
