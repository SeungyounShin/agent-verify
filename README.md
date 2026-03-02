# agent-verify

Systematic evaluation of agentic coding harnesses on [SWE-bench](https://www.swebench.com/). Compares verification strategies, scaling configurations, and search algorithms across models.

## Experiments

| # | Description | Model | Benchmark | Result |
|---|-------------|-------|-----------|--------|
| 1 | [Verification: V0 (none) vs V2 (test execution)](exp-log/EXPERIMENTS.md#results) | Claude Sonnet 4.6 / Qwen 3.5 397B | Verified (10 tasks) | 6/10, 5/10 |
| 2 | [Qwen V0 baseline](exp-log/EXPERIMENTS.md#experiment-2-qwen-v0-on-swe-bench-lite-dev-23-tasks) | Qwen 3.5 397B | Lite dev (23) | 4/23 (17.4%) |
| 3 | [Unlimited budget (no compaction)](exp-log/EXPERIMENTS.md#experiment-3-unlimited-budget-no-compaction-on-swe-bench-lite-dev) | Qwen 3.5 397B | Lite dev (23) | 7/23 (30.4%) |
| 4 | [Auto-compaction (32K context)](exp-log/EXPERIMENTS.md#experiment-4-auto-compaction-32k-context-on-swe-bench-lite-dev) | Qwen 3.5 397B | Lite dev (23) | 7/23 (30.4%) |
| 5 | [128K context + task context](exp-log/EXPERIMENTS.md#experiment-5-128k-context--task-context--max-steps-2000) | Qwen 3.5 397B | Lite dev (23) | 8/23 (34.8%) |
| 6 | [Enhanced ACI tools](exp-log/EXPERIMENTS.md#experiment-6-enhanced-agent-computer-interface-aci) | Qwen 3.5 397B | Lite dev (23) | 6/23 (26.1%) |
| 8 | [Full-scale 200-step](exp-log/EXPERIMENTS.md#experiment-8-qwen35-35b-a3b-on-swe-bench-verified-500-tasks) | Qwen3.5-35B-A3B | Verified (500) | 314/500 (62.8%) |
| 9 | [100-step compaction](exp-log/EXPERIMENTS.md#experiment-9-100-step-compaction-on-swe-bench-verified-500-tasks) | Qwen3.5-35B-A3B | Verified (500) | 320/500 (64.0%) |
| — | [Hard subset comparison](exp-log/swebench_verified_hard.md) | Opus 4.6 vs Qwen3.5-35B-A3B | Verified Hard (45) | 18/45 (40.0%) |

## Structure

```
configs/experiments/   # YAML experiment configs
scripts/               # Experiment runners, docker eval, MCTS agents
src/agent_verify/      # Core harness: LLM clients, tools, context, logging
exp-log/               # Experiment reports and results
results/               # Raw outputs, patches, traces
```

## Quick Start

```bash
# Run an experiment
uv run python scripts/run_compaction_experiment.py --config configs/experiments/<config>.yaml

# Docker evaluation
uv run python scripts/docker_eval.py --patch-dir results/<exp>/patches --run-name <name> \
    --dataset princeton-nlp/SWE-bench_Verified --split test --max-workers 10
```
