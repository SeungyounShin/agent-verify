#!/usr/bin/env python3
"""
Error analysis for Experiment 8: Qwen3.5-35B on SWE-bench Verified (500 tasks).
Analyzes the ~186 failed tasks to understand failure modes.
"""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
DOCKER_REPORT = "exp-log/docker_reports/exp8_final.exp8_final.json"
LOG_FILE = "results/exp8_qwen35b_verified/exp8_qwen35b_verified_log.jsonl"
PATCHES_DIR = "results/exp8_qwen35b_verified/patches"

BASE = Path(__file__).resolve().parent.parent
DOCKER_REPORT = BASE / DOCKER_REPORT
LOG_FILE = BASE / LOG_FILE
PATCHES_DIR = BASE / PATCHES_DIR


def load_data():
    with open(DOCKER_REPORT) as f:
        report = json.load(f)

    # Load log (take last entry per task_id in case of duplicates)
    log = {}
    with open(LOG_FILE) as f:
        for line in f:
            d = json.loads(line)
            log[d["task_id"]] = d

    # Load patches: task_id -> patch text
    patches = {}
    for p in PATCHES_DIR.iterdir():
        if p.suffix == ".diff":
            task_id = p.stem
            patches[task_id] = p.read_text()

    return report, log, patches


def extract_repo(task_id: str) -> str:
    """e.g. 'django__django-10097' -> 'django/django'"""
    parts = task_id.split("__")
    owner = parts[0]
    rest = parts[1]  # 'django-10097'
    repo_name = "-".join(rest.split("-")[:-1])
    return f"{owner}/{repo_name}"


def patch_lines(text: str) -> int:
    """Count non-header diff lines (lines starting with + or - but not +++ or ---)."""
    count = 0
    for line in text.splitlines():
        if (line.startswith("+") and not line.startswith("+++")) or \
           (line.startswith("-") and not line.startswith("---")):
            count += 1
    return count


def fmt_pct(n, total):
    return f"{n:>4d} / {total:<4d} ({100*n/total:5.1f}%)" if total else "   0 /    0 (  N/A)"


def print_separator(title: str):
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)


def main():
    report, log, patches = load_data()

    resolved_ids = set(report["resolved_ids"])
    unresolved_ids = set(report["unresolved_ids"])
    error_ids = set(report["error_ids"])
    empty_patch_ids = set(report["empty_patch_ids"])
    submitted_ids = set(report["submitted_ids"])

    # All tasks that were submitted to docker eval
    all_eval_ids = submitted_ids
    failed_ids = all_eval_ids - resolved_ids  # everything not resolved

    # Tasks in log but NOT submitted to docker (not part of the 500-task subset
    # used for eval, or missing patches, etc.)
    log_ids = set(log.keys())
    # Tasks submitted but not in log (shouldn't happen, but let's check)
    eval_not_in_log = all_eval_ids - log_ids
    log_not_in_eval = log_ids - all_eval_ids

    total_submitted = len(all_eval_ids)
    total_resolved = len(resolved_ids)
    total_failed = len(failed_ids)

    # ── Header ─────────────────────────────────────────────────────────────
    print_separator("EXPERIMENT 8 ERROR ANALYSIS — Qwen3.5-35B on SWE-bench Verified")
    print(f"  Total submitted to Docker eval:  {total_submitted}")
    print(f"  Resolved:                        {fmt_pct(total_resolved, total_submitted)}")
    print(f"  Failed:                          {fmt_pct(total_failed, total_submitted)}")
    print(f"  Tasks in agent log:              {len(log_ids)}")
    print()
    print(f"  NOTE: Docker eval received 471 of ~500 tasks (some may have failed to")
    print(f"  produce patches or were excluded). 26 log entries have no docker result.")
    if eval_not_in_log:
        print(f"  WARNING: {len(eval_not_in_log)} submitted tasks have no log entry")
    if log_not_in_eval:
        print(f"  Note: {len(log_not_in_eval)} log entries not in docker eval submission")

    # ── 1. Failure Category Breakdown ──────────────────────────────────────
    print_separator("1. FAILURE CATEGORY BREAKDOWN")

    # Categorize each failed task
    cat_max_steps = set()
    cat_agent_declared_wrong = set()
    cat_llm_error = set()
    cat_empty_patch = set()
    cat_no_log = set()

    for tid in failed_ids:
        if tid in empty_patch_ids:
            cat_empty_patch.add(tid)
        elif tid in error_ids:
            cat_llm_error.add(tid)  # docker error (may overlap with llm_error)
        elif tid not in log:
            cat_no_log.add(tid)
        else:
            reason = log[tid]["completion_reason"]
            if reason == "max_steps":
                cat_max_steps.add(tid)
            elif reason == "agent_declared":
                cat_agent_declared_wrong.add(tid)
            elif reason == "llm_error":
                cat_llm_error.add(tid)
            else:
                cat_max_steps.add(tid)  # fallback

    # Also check for tasks that produced empty patches but aren't in empty_patch_ids
    for tid in failed_ids:
        if tid in log and tid not in cat_empty_patch:
            patch_text = patches.get(tid, "")
            if not patch_text.strip():
                # Re-categorize: still keep the completion_reason but note it
                pass

    categories = [
        ("max_steps (hit 200-step limit)", cat_max_steps),
        ("agent_declared (said TASK_COMPLETE but wrong)", cat_agent_declared_wrong),
        ("llm_error / docker error", cat_llm_error),
        ("empty_patch (no diff produced)", cat_empty_patch),
        ("no log entry", cat_no_log),
    ]

    for label, ids in categories:
        print(f"  {label:50s}  {fmt_pct(len(ids), total_failed)}")

    # ── 2. Per-Repo Failure Analysis ───────────────────────────────────────
    print_separator("2. PER-REPO FAILURE ANALYSIS")

    repo_total = Counter()
    repo_resolved = Counter()
    repo_failed = Counter()

    for tid in all_eval_ids:
        repo = extract_repo(tid)
        repo_total[repo] += 1
        if tid in resolved_ids:
            repo_resolved[repo] += 1
        else:
            repo_failed[repo] += 1

    # Sort by failure count descending
    repos_sorted = sorted(repo_total.keys(), key=lambda r: (-repo_failed[r], r))

    print(f"  {'Repo':<35s} {'Total':>5s} {'Resolved':>8s} {'Failed':>6s} {'Rate':>7s}")
    print(f"  {'-'*35} {'-'*5} {'-'*8} {'-'*6} {'-'*7}")
    for repo in repos_sorted:
        t = repo_total[repo]
        r = repo_resolved[repo]
        fl = repo_failed[repo]
        rate = 100 * r / t if t else 0
        print(f"  {repo:<35s} {t:>5d} {r:>8d} {fl:>6d} {rate:>6.1f}%")

    # ── 3. Failed Task Characteristics ─────────────────────────────────────
    print_separator("3. FAILED TASK CHARACTERISTICS")

    def stats_for_ids(ids, label):
        entries = [log[tid] for tid in ids if tid in log]
        if not entries:
            print(f"  {label}: no log entries")
            return
        n = len(entries)
        avg_steps = sum(e["total_steps"] for e in entries) / n
        avg_input = sum(e["total_input_tokens"] for e in entries) / n
        avg_output = sum(e["total_output_tokens"] for e in entries) / n
        avg_wall = sum(e["wall_clock_seconds"] for e in entries) / n
        avg_compactions = sum(e["compactions"] for e in entries) / n
        median_steps = sorted(e["total_steps"] for e in entries)[n // 2]
        print(f"  {label} (n={n}):")
        print(f"    Avg steps:          {avg_steps:>8.1f}   (median: {median_steps})")
        print(f"    Avg input tokens:   {avg_input:>12,.0f}")
        print(f"    Avg output tokens:  {avg_output:>12,.0f}")
        print(f"    Avg wall clock:     {avg_wall:>8.1f}s  ({avg_wall/60:.1f} min)")
        print(f"    Avg compactions:    {avg_compactions:>8.1f}")

    stats_for_ids(resolved_ids, "RESOLVED tasks")
    print()
    stats_for_ids(failed_ids, "FAILED tasks")

    # Interesting: how many resolved tasks also hit max_steps?
    resolved_max_steps = sum(1 for tid in resolved_ids if tid in log and log[tid]["completion_reason"] == "max_steps")
    resolved_declared = sum(1 for tid in resolved_ids if tid in log and log[tid]["completion_reason"] == "agent_declared")
    print()
    print(f"  Among RESOLVED tasks: {resolved_declared} agent_declared, {resolved_max_steps} max_steps")
    print(f"  (max_steps resolved = agent ran out of steps but its last patch was correct)")

    print()
    print("  Completion reason distribution among FAILED tasks:")
    reason_counts = Counter()
    for tid in failed_ids:
        if tid in log:
            reason_counts[log[tid]["completion_reason"]] += 1
        else:
            reason_counts["(no log)"] += 1
    for reason, cnt in reason_counts.most_common():
        print(f"    {reason:<25s}  {fmt_pct(cnt, total_failed)}")

    # ── 4. Patch Analysis ──────────────────────────────────────────────────
    print_separator("4. PATCH ANALYSIS")

    failed_with_patch = set()
    failed_empty_patch = set()
    failed_patch_sizes = []
    resolved_patch_sizes = []

    for tid in all_eval_ids:
        patch_text = patches.get(tid, "")
        plines = patch_lines(patch_text)
        is_empty = not patch_text.strip()

        if tid in resolved_ids:
            resolved_patch_sizes.append(plines)
        else:
            if is_empty:
                failed_empty_patch.add(tid)
            else:
                failed_with_patch.add(tid)
            failed_patch_sizes.append(plines)

    print(f"  Failed tasks with non-empty patch (tried but wrong): {fmt_pct(len(failed_with_patch), total_failed)}")
    print(f"  Failed tasks with empty/no patch (gave up):          {fmt_pct(len(failed_empty_patch), total_failed)}")
    print()

    if resolved_patch_sizes:
        avg_res = sum(resolved_patch_sizes) / len(resolved_patch_sizes)
        med_res = sorted(resolved_patch_sizes)[len(resolved_patch_sizes) // 2]
        print(f"  Resolved — avg patch size: {avg_res:.1f} changed lines (median: {med_res})")
    if failed_patch_sizes:
        avg_fail = sum(failed_patch_sizes) / len(failed_patch_sizes)
        med_fail = sorted(failed_patch_sizes)[len(failed_patch_sizes) // 2]
        print(f"  Failed   — avg patch size: {avg_fail:.1f} changed lines (median: {med_fail})")

    # Breakdown: among failed-with-patch, how big are the patches?
    nonempty_sizes = [patch_lines(patches.get(tid, "")) for tid in failed_with_patch]
    if nonempty_sizes:
        nonempty_sizes.sort()
        print()
        print(f"  Among failed tasks with non-empty patches (n={len(nonempty_sizes)}):")
        print(f"    Min: {nonempty_sizes[0]}, Median: {nonempty_sizes[len(nonempty_sizes)//2]}, "
              f"Max: {nonempty_sizes[-1]}, Avg: {sum(nonempty_sizes)/len(nonempty_sizes):.1f}")

    # ── 5. Close Misses ────────────────────────────────────────────────────
    print_separator("5. CLOSE MISSES — agent_declared + non-empty patch + not resolved")

    close_misses = []
    for tid in cat_agent_declared_wrong:
        patch_text = patches.get(tid, "")
        if patch_text.strip():
            plines = patch_lines(patch_text)
            steps = log[tid]["total_steps"] if tid in log else "?"
            wall = log[tid]["wall_clock_seconds"] if tid in log else 0
            close_misses.append((tid, plines, steps, wall))

    close_misses.sort(key=lambda x: x[1])  # sort by patch size

    print(f"  Total close misses: {len(close_misses)}")
    print()
    print(f"  {'Task ID':<45s} {'Patch lines':>11s} {'Steps':>6s} {'Time':>8s}")
    print(f"  {'-'*45} {'-'*11} {'-'*6} {'-'*8}")
    for tid, plines, steps, wall in close_misses:
        print(f"  {tid:<45s} {plines:>11d} {steps:>6} {wall:>7.0f}s")

    # ── 6. Hardest Repos ───────────────────────────────────────────────────
    print_separator("6. HARDEST REPOS — zero resolve rate")

    zero_repos = [r for r in repos_sorted if repo_resolved[r] == 0 and repo_total[r] > 0]
    if zero_repos:
        print(f"  {'Repo':<35s} {'Total tasks':>11s}")
        print(f"  {'-'*35} {'-'*11}")
        for repo in zero_repos:
            print(f"  {repo:<35s} {repo_total[repo]:>11d}")
        print()
        # List all task IDs in zero-resolve repos
        print("  Task IDs in zero-resolve repos:")
        for repo in zero_repos:
            tids = sorted(tid for tid in failed_ids if extract_repo(tid) == repo)
            for tid in tids:
                reason = log[tid]["completion_reason"] if tid in log else "no_log"
                has_patch = "patch" if patches.get(tid, "").strip() else "no_patch"
                print(f"    {tid:<45s}  {reason:<18s}  {has_patch}")
    else:
        print("  Every repo has at least one resolved task!")

    # ── 7. Summary ─────────────────────────────────────────────────────────
    print_separator("7. SUMMARY & KEY TAKEAWAYS")

    pct_max = 100 * len(cat_max_steps) / total_failed if total_failed else 0
    pct_wrong = 100 * len(cat_agent_declared_wrong) / total_failed if total_failed else 0
    pct_close = 100 * len(close_misses) / total_failed if total_failed else 0

    print(f"  - {pct_max:.0f}% of failures are max_steps (agent ran out of steps)")
    print(f"  - {pct_wrong:.0f}% of failures are false completions (agent thought it was done)")
    print(f"  - {pct_close:.0f}% of failures are close misses (declared done + non-empty patch)")
    print(f"  - {len(failed_with_patch)} of {total_failed} failed tasks produced a patch")
    if zero_repos:
        print(f"  - {len(zero_repos)} repos had 0% resolve rate: {', '.join(zero_repos)}")
    print()


if __name__ == "__main__":
    main()
