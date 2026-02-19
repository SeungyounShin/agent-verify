#!/usr/bin/env python3
"""Explore SWE-bench Verified dataset to pick a good smoke test task."""

from datasets import load_dataset


def main():
    print("Loading SWE-bench Verified...")
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    print(f"Total instances: {len(ds)}")
    print(f"Columns: {ds.column_names}")
    print()

    # Show repo distribution
    repos = {}
    for row in ds:
        repo = row["repo"]
        repos[repo] = repos.get(repo, 0) + 1

    print("Top repos:")
    for repo, count in sorted(repos.items(), key=lambda x: -x[1])[:15]:
        print(f"  {repo}: {count}")
    print()

    # Find smaller/simpler tasks (short problem statements, python repos)
    simple_tasks = []
    for row in ds:
        desc_len = len(row.get("problem_statement", ""))
        patch_len = len(row.get("patch", ""))
        if patch_len < 500 and desc_len < 2000:
            simple_tasks.append({
                "instance_id": row["instance_id"],
                "repo": row["repo"],
                "desc_len": desc_len,
                "patch_len": patch_len,
                "problem": row["problem_statement"][:200],
            })

    simple_tasks.sort(key=lambda x: x["patch_len"])
    print(f"\nSmallest patches ({len(simple_tasks)} tasks with patch < 500 chars):")
    for t in simple_tasks[:10]:
        print(f"\n  ID: {t['instance_id']}")
        print(f"  Repo: {t['repo']}")
        print(f"  Patch size: {t['patch_len']} chars")
        print(f"  Problem: {t['problem'][:150]}...")


if __name__ == "__main__":
    main()
