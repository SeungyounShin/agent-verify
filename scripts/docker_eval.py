"""Docker-based SWE-bench evaluation using official swebench package.

Runs evaluation in parallel using Docker containers with pre-built images.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from datasets import load_dataset
from swebench.harness.run_evaluation import main as run_evaluation


def extract_source_only_patch(diff: str, task_id: str) -> str:
    """Filter a git diff to only include non-test file changes.

    SWE-bench applies its own test_patch, so we should only include
    the agent's source code fixes in the model_patch.
    """
    if not diff.strip():
        return ""

    # Split diff into per-file sections
    file_diffs = re.split(r'(?=^diff --git )', diff, flags=re.MULTILINE)

    source_diffs = []
    for fd in file_diffs:
        if not fd.strip():
            continue
        # Extract file path from diff header
        match = re.search(r'diff --git a/(.*?) b/', fd)
        if not match:
            continue
        filepath = match.group(1)

        # Skip test files
        if _is_test_file(filepath):
            continue

        source_diffs.append(fd)

    return ''.join(source_diffs)


def _is_test_file(filepath: str) -> bool:
    """Check if a file path is a test file."""
    parts = filepath.split('/')
    basename = parts[-1] if parts else filepath

    # Common test file patterns
    if basename.startswith('test_') or basename.endswith('_test.py'):
        return True
    if 'tests/' in filepath or 'test/' in filepath or 'testing/' in filepath:
        return True
    if basename == 'conftest.py':
        return True
    return False


def build_predictions(patch_dir: str, instance_ids: list[str], run_name: str) -> str:
    """Build predictions JSON file from saved patches.

    Returns path to predictions file.
    """
    predictions = []

    for instance_id in instance_ids:
        diff_path = Path(patch_dir) / f"{instance_id}.diff"
        if not diff_path.exists():
            print(f"WARNING: No patch found for {instance_id}, skipping")
            continue

        full_diff = diff_path.read_text()
        source_diff = extract_source_only_patch(full_diff, instance_id)

        if not source_diff.strip():
            print(f"WARNING: No source changes for {instance_id} (only test changes)")
            # Still include with empty patch - will fail evaluation but that's correct
            source_diff = ""

        predictions.append({
            "instance_id": instance_id,
            "model_name_or_path": run_name,
            "model_patch": source_diff,
        })

        # Print summary
        full_files = re.findall(r'diff --git a/(.*?) b/', full_diff)
        source_files = re.findall(r'diff --git a/(.*?) b/', source_diff)
        filtered = set(full_files) - set(source_files)
        print(f"  {instance_id}: {len(source_files)} source files"
              f"{f' (filtered {len(filtered)} test files)' if filtered else ''}")

    # Write predictions file
    pred_path = Path(patch_dir).parent / f"{run_name}_predictions.json"
    pred_path.write_text(json.dumps(predictions, indent=2))
    print(f"\nPredictions saved to {pred_path} ({len(predictions)} instances)")
    return str(pred_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Docker-based SWE-bench evaluation")
    parser.add_argument("--patch-dir", required=True, help="Directory with .diff files")
    parser.add_argument("--run-name", default="v2_agent", help="Name for this run")
    parser.add_argument("--max-workers", type=int, default=10, help="Parallel containers")
    parser.add_argument("--timeout", type=int, default=900, help="Per-instance timeout (s)")
    parser.add_argument("--instance-ids", nargs="+", help="Specific instance IDs to evaluate")
    parser.add_argument("--report-dir", default="results/v0_vs_v2/docker_eval", help="Output dir")
    args = parser.parse_args()

    # Discover instance IDs from patch files if not specified
    if args.instance_ids:
        instance_ids = args.instance_ids
    else:
        patch_dir = Path(args.patch_dir)
        instance_ids = sorted([
            p.stem for p in patch_dir.glob("*.diff")
            if p.stat().st_size > 0
        ])

    print(f"Evaluating {len(instance_ids)} instances with Docker (max_workers={args.max_workers})")
    print(f"Instances: {instance_ids}\n")

    # Build predictions file
    pred_path = build_predictions(args.patch_dir, instance_ids, args.run_name)

    # Create report directory
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    # Run SWE-bench Docker evaluation
    print(f"\n{'='*60}")
    print(f"Starting Docker evaluation ({args.max_workers} parallel containers)")
    print(f"{'='*60}\n")

    run_evaluation(
        dataset_name="princeton-nlp/SWE-bench_Verified",
        split="test",
        instance_ids=instance_ids,
        predictions_path=pred_path,
        max_workers=args.max_workers,
        force_rebuild=False,
        cache_level="env",
        clean=False,
        open_file_limit=4096,
        run_id=args.run_name,
        timeout=args.timeout,
        namespace="swebench",
        rewrite_reports=False,
        modal=False,
        report_dir=str(report_dir),
    )

    # Parse results
    print(f"\n{'='*60}")
    print("Evaluation Results")
    print(f"{'='*60}")

    # Look for result reports
    results_dir = report_dir / args.run_name
    if results_dir.exists():
        for result_file in sorted(results_dir.glob("*.json")):
            print(f"\n{result_file.name}:")
            data = json.loads(result_file.read_text())
            print(json.dumps(data, indent=2)[:2000])
    else:
        # Check alternative paths
        for p in report_dir.rglob("*.json"):
            print(f"\nFound: {p}")
            data = json.loads(p.read_text())
            if isinstance(data, dict):
                for k, v in data.items():
                    print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
