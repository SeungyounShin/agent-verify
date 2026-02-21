# Experiment Log — Self-Verification in Agentic Coding Harnesses

## Overview

Systematic comparison of verification strategies (V0: none vs V2: test execution) across two models (Claude Sonnet 4.6 vs Qwen 3.5 397B) on SWE-bench Verified.

- **Benchmark**: SWE-bench Verified (10 tasks, 10 distinct repos)
- **Evaluation**: Docker-based using official `swebench` package images
- **Execution**: 10 tasks in parallel (async ThreadPoolExecutor)

---

## Models

| Model | Provider | Params | Cost |
|---|---|---|---|
| Claude Sonnet 4.6 | Anthropic API | — | ~$0.19/task |
| Qwen 3.5 397B (FP8 MoE) | vLLM on H100x8 (local) | 397B (17B active) | $0 (self-hosted) |

## Verification Methods

| Method | Description |
|---|---|
| **V0 (None)** | Agent declares `TASK_COMPLETE` → harness accepts |
| **V2 (Test Execution)** | Agent declares done → harness runs tests → if fail, provides feedback → agent retries (max 3 recovery attempts) |

---

## Results

### Docker Evaluation (SWE-bench Verified, 10 tasks)

```
Task                                    Claude V0  Claude V2    Qwen V0    Qwen V2
─────────────────────────────────────────────────────────────────────────────────────
astropy__astropy-14365                       FAIL       PASS       FAIL       FAIL
django__django-16950                         PASS      EMPTY       FAIL        N/A
matplotlib__matplotlib-24637                 PASS       PASS       PASS       PASS
psf__requests-2931                           FAIL       FAIL       FAIL       PASS
pydata__xarray-6599                          PASS       PASS       PASS       FAIL
pylint-dev__pylint-7277                      PASS       PASS       PASS       PASS
pytest-dev__pytest-5631                     EMPTY      EMPTY      EMPTY       FAIL
scikit-learn__scikit-learn-14983             PASS       PASS       FAIL       PASS
sphinx-doc__sphinx-10435                      N/A       FAIL        N/A       FAIL
sympy__sympy-19346                           PASS       PASS       PASS       PASS
─────────────────────────────────────────────────────────────────────────────────────
Resolved / Total                             6/10       6/10       4/10       5/10
Resolved / Evaluated                         6/8        6/8        4/8        5/9
Resolve % (evaluated)                         75%        75%        50%        56%
Cost                                       ~$1.90     ~$3.87         $0         $0
```

### Summary Metrics

| Metric | Claude V0 | Claude V2 | Qwen V0 | Qwen V2 |
|---|---|---|---|---|
| **Resolve Rate** | 6/10 (60%) | 6/10 (60%) | 4/10 (40%) | 5/10 (50%) |
| **Resolve % (evaluated only)** | 75% | 75% | 50% | 56% |
| **Total Cost** | $1.90 | $3.87 | $0 | $0 |
| **V0→V2 Delta** | +0 | — | +1 | — |
| **Avg Iterations** | ~22 | 40 (all maxed) | ~25 | ~35 |
| **Cache Hit Rate** | 82.5% | 90.0% | N/A | N/A |

---

## Key Findings

### 1. Test-execution verification (V2) provides marginal benefit at 2x cost

- **Claude**: V0 and V2 have identical resolve rates (6/10). V2 costs 2x ($3.87 vs $1.90) due to recovery loops.
- **Qwen**: V2 improves by +1 task (4→5), resolving `psf__requests-2931` which V0 missed.
- **Interpretation**: For strong models (Claude), V2's test feedback adds noise more than signal. For weaker models (Qwen), the feedback provides corrective value.

### 2. Claude Sonnet 4.6 significantly outperforms Qwen 3.5 397B

- Claude resolves 75% of evaluated tasks vs Qwen's 50-56%.
- Claude generates correct source patches more consistently.
- Qwen frequently runs out of time/tokens without completing (timeout, token_budget).

### 3. V2 verification can be harmful

- Claude V2 lost `django__django-16950` (produced empty source patch) — V2 test failures confused the agent into only modifying test files.
- Qwen V2 lost `pydata__xarray-6599` (was resolved in V0) — recovery loops degraded the correct fix.

### 4. Local model (Qwen) achieves decent results at zero API cost

- Qwen V2 resolves 5/10 tasks for free on local H100x8 hardware.
- With interleaved reasoning support and extended timeout (1800s), Qwen generates patches for 9/10 tasks.

---

## Configuration Details

### Claude Experiments

- `max_iterations`: 40
- `max_tokens_budget`: 500,000
- `timeout_seconds`: 600
- `temperature`: 0.0
- Prompt caching: system prompt + tools + conversation history (2nd-to-last user turn)

### Qwen Experiments

- `max_iterations`: 40
- `max_tokens_budget`: 1,000,000
- `timeout_seconds`: 1,800
- `temperature`: 0.6
- `max_tokens` (per response): 32,768
- Interleaved reasoning: preserved across turns via `reasoning` field in vLLM API
- Model: `/raid/robin/models/Qwen3.5-397B-A17B-FP8` served by vLLM 0.16.0rc2

### Task Selection (10 diverse repos)

| Task ID | Repo |
|---|---|
| `django__django-16950` | django/django |
| `sympy__sympy-19346` | sympy/sympy |
| `scikit-learn__scikit-learn-14983` | scikit-learn/scikit-learn |
| `matplotlib__matplotlib-24637` | matplotlib/matplotlib |
| `pytest-dev__pytest-5631` | pytest-dev/pytest |
| `sphinx-doc__sphinx-10435` | sphinx-doc/sphinx |
| `pydata__xarray-6599` | pydata/xarray |
| `astropy__astropy-14365` | astropy/astropy |
| `psf__requests-2931` | psf/requests |
| `pylint-dev__pylint-7277` | pylint-dev/pylint |

---

## Infrastructure

- **Docker Evaluation**: Official `swebench` package with pre-built Docker images from Docker Hub (`swebench/sweb.eval.x86_64.*`)
- **Parallel Execution**: 10 tasks run concurrently via `ThreadPoolExecutor` (harness) and `max_workers=10` (Docker eval)
- **Agent Tools**: `file_read`, `file_write`, `file_edit`, `bash` (with blocked `pip install` commands)
- **Patch Processing**: Test file changes are filtered out before Docker eval (gold `test_patch` applied by SWE-bench)

## Files

- `exp-log/results.json` — Consolidated results (machine-readable)
- `results/v0_vs_v2/` — Claude experiment raw data, patches, Docker eval reports
- `results/qwen_vs_claude/` — Qwen experiment raw data, patches, Docker eval reports
- `configs/experiments/` — YAML experiment configurations
- `scripts/run_experiment.py` — Parallel experiment runner
- `scripts/docker_eval.py` — Docker-based SWE-bench evaluation
