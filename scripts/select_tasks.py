#!/usr/bin/env python3
"""Select 10 diverse, solvable tasks for V0 vs V2 experiment."""

import json
from collections import defaultdict
from datasets import load_dataset


def main():
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")

    # Filter: must have FAIL_TO_PASS tests and reasonable patch size
    candidates = []
    for row in ds:
        fail_to_pass = row.get("FAIL_TO_PASS", "")
        patch = row.get("patch", "")
        test_patch = row.get("test_patch", "")
        patch_len = len(patch)

        # Must have test info
        if not fail_to_pass or not test_patch:
            continue

        # Reasonable patch size: not trivial, not huge
        if patch_len < 100 or patch_len > 3000:
            continue

        candidates.append({
            "instance_id": row["instance_id"],
            "repo": row["repo"],
            "patch_len": patch_len,
            "desc_len": len(row.get("problem_statement", "")),
            "difficulty": row.get("difficulty", ""),
        })

    print(f"Candidates after filtering: {len(candidates)}")

    # Group by repo
    by_repo = defaultdict(list)
    for c in candidates:
        by_repo[c["repo"]].append(c)

    print("\nRepo distribution:")
    for repo, tasks in sorted(by_repo.items(), key=lambda x: -len(x[1])):
        print(f"  {repo}: {len(tasks)}")

    # Select 10 tasks: spread across repos, prefer medium patch size
    selected = []
    # Priority repos (most common in SWE-bench, well-supported)
    priority_repos = [
        "django/django",
        "sympy/sympy",
        "scikit-learn/scikit-learn",
        "matplotlib/matplotlib",
        "pytest-dev/pytest",
        "sphinx-doc/sphinx",
        "pydata/xarray",
        "astropy/astropy",
        "psf/requests",
        "pylint-dev/pylint",
    ]

    for repo in priority_repos:
        if len(selected) >= 10:
            break
        tasks = by_repo.get(repo, [])
        if not tasks:
            continue
        # Pick the one with medium patch size
        tasks.sort(key=lambda x: x["patch_len"])
        mid = len(tasks) // 2
        selected.append(tasks[mid])

    # Fill remaining slots from other repos
    remaining = [c for c in candidates if c not in selected]
    remaining.sort(key=lambda x: x["patch_len"])
    for c in remaining:
        if len(selected) >= 10:
            break
        if c["repo"] not in [s["repo"] for s in selected]:
            selected.append(c)

    print(f"\n{'='*60}")
    print(f"Selected {len(selected)} tasks:")
    print(f"{'='*60}")
    ids = []
    for s in selected:
        print(f"  {s['instance_id']}")
        print(f"    repo={s['repo']}  patch={s['patch_len']}chars  difficulty={s['difficulty']}")
        ids.append(s["instance_id"])

    print(f"\nYAML format:")
    print("instance_ids:")
    for id_ in ids:
        print(f'  - "{id_}"')


if __name__ == "__main__":
    main()
