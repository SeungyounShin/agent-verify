# SWE-bench Verified Hard — Model Comparison

**45 tasks rated 1–4 hours or >4 hours fix time · March 2026**

## Summary

| Metric | Claude Opus 4.6 | Qwen E12 (edit-nudge) | Qwen E11v2 (prompt v2) | Qwen E9 (100 steps) | Qwen E8 (200 steps) |
|--------|----------------:|----------------------:|-----------------------:|---------------------:|---------------------:|
| Resolved | **18/45 (40.0%)** | 17/45 (37.8%) | 15/45 (33.3%) | 10/45 (22.2%) | 8/45 (17.8%) |
| Agent completed | 39/45 (86.7%) | — | 30/45 (66.7%) | — | — |
| Has patch | 44/45 (97.8%) | 45/45 (100%) | — | — | — |
| Total cost | $62.29 | $0 (local) | $0 (local) | $0 (local) | $0 (local) |
| Exclusive solves | **3** | 2 | 2 | 0 | 0 |
| Union (Opus + E12) | **25/45 (55.6%)** | | | | |
| Union (all models) | **27/45 (60.0%)** | | | | |

> **E12 (edit-nudge) nearly matches Opus**: 17/45 (37.8%) vs 18/45 (40.0%). The edit-nudge strategy — injecting a user message after each `file_edit` to force immediate verification via inline test or /tmp script — picks up 7 new solves across diverse repos (astropy, django, pytest, sklearn, sphinx). Union of all Qwen strategies + Opus = **27/45 (60.0%)**.

## Strategy Descriptions

| Experiment | Strategy |
|---|---|
| **E8** | ACI workflow prompt, 200 steps, auto-compaction |
| **E9** | ACI workflow prompt, 100 steps (tighter budget forces efficiency) |
| **E11v2** | Simplified prompt (no rigid workflow), verify script required before TASK_COMPLETE, "TASK_COMPLETE as plain text" instruction |
| **E12** | E11v2 + `--edit-nudge`: after each successful `file_edit`, inject user message forcing agent to immediately test the change via `python -c` or /tmp script |

## Per-Repository Breakdown

| Repository | Tasks | Opus | E12 | E11v2 | E9 | E8 |
|------------|------:|-----:|----:|------:|---:|---:|
| django/django | 22 | **10** | 9 | 9 | 5 | 4 |
| sympy/sympy | 7 | 2 | **2** | **3** | 0 | 1 |
| sphinx-doc/sphinx | 5 | 1 | **2** | 1 | 0 | 0 |
| astropy/astropy | 3 | 1 | **2** | 1 | 1 | 1 |
| pytest-dev/pytest | 3 | 1 | **1** | 0 | 1 | 1 |
| scikit-learn | 1 | **1** | **1** | 0 | 0 | 1 |
| pydata/xarray | 2 | **1** | 0 | 0 | 0 | 0 |
| pylint-dev/pylint | 2 | 0 | 0 | 0 | 0 | 0 |

## Per-Task Results

| Task ID | Difficulty | Opus | E12 | E11v2 | E9 | E8 |
|---------|-----------|:----:|:---:|:-----:|:--:|:--:|
| `astropy__astropy-13398` | >4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `astropy__astropy-13579` | 1-4h | ✓ | ✓ | ✓ | ✓ | ✓ |
| `astropy__astropy-14369` | 1-4h | ✗ | **✓** | ✗ | ✗ | ✗ |
| `django__django-10554` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `django__django-11138` | 1-4h | ✓ | ✗ | ✗ | ✓ | ✗ |
| `django__django-11400` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `django__django-11885` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `django__django-12325` | 1-4h | ✗ | **✓** | ✗ | ✗ | ✗ |
| `django__django-12708` | 1-4h | ✓ | ✓ | ✓ | ✓ | ✓ |
| `django__django-13128` | 1-4h | ✓ | ✓ | ✓ | ✓ | ✗ |
| `django__django-13212` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `django__django-13344` | 1-4h | ✗ | ✗ | ✓ | ✗ | ✗ |
| `django__django-13449` | 1-4h | ✓ | ✓ | ✓ | ✓ | ✗ |
| `django__django-13837` | 1-4h | ✓ | ✓ | ✓ | ✓ | ✗ |
| `django__django-14007` | 1-4h | ✓ | ✓ | ✓ | ✓ | ✓ |
| `django__django-14011` | >4h | ✗ | ✗ | ✓ | ✗ | ✗ |
| `django__django-14631` | 1-4h | ✓ | ✓ | ✓ | ✓ | ✓ |
| `django__django-15128` | 1-4h | ✓ | ✗ | ✓ | ✗ | ✗ |
| `django__django-15268` | 1-4h | ✓ | ✗ | ✗ | ✓ | ✓ |
| `django__django-15503` | 1-4h | ✓ | **✓** | ✗ | ✗ | ✗ |
| `django__django-15629` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `django__django-15957` | 1-4h | ✓ | ✗ | ✗ | ✗ | ✗ |
| `django__django-16263` | 1-4h | ✗ | ✗ | ✓ | ✗ | ✗ |
| `django__django-16560` | 1-4h | ✗ | **✓** | ✗ | ✗ | ✗ |
| `django__django-16631` | >4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `pydata__xarray-3993` | 1-4h | ✓ | ✗ | ✗ | ✗ | ✗ |
| `pydata__xarray-6992` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `pylint-dev__pylint-4551` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `pylint-dev__pylint-8898` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `pytest-dev__pytest-10356` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `pytest-dev__pytest-5787` | 1-4h | ✗ | **✓** | ✗ | ✗ | ✗ |
| `pytest-dev__pytest-6197` | 1-4h | ✓ | ✗ | ✗ | ✓ | ✓ |
| `scikit-learn__scikit-learn-25102` | 1-4h | ✓ | **✓** | ✗ | ✗ | ✓ |
| `sphinx-doc__sphinx-11510` | 1-4h | ✗ | ✓ | ✓ | ✗ | ✗ |
| `sphinx-doc__sphinx-7590` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `sphinx-doc__sphinx-8548` | 1-4h | ✓ | **✓** | ✗ | ✗ | ✗ |
| `sphinx-doc__sphinx-9229` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `sphinx-doc__sphinx-9461` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `sympy__sympy-12489` | 1-4h | ✓ | ✗ | ✓ | ✗ | ✓ |
| `sympy__sympy-13852` | 1-4h | ✗ | ✓ | ✓ | ✗ | ✗ |
| `sympy__sympy-13878` | 1-4h | ✓ | ✓ | ✓ | ✗ | ✗ |
| `sympy__sympy-14248` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `sympy__sympy-16597` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `sympy__sympy-17630` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |
| `sympy__sympy-18199` | 1-4h | ✗ | ✗ | ✗ | ✗ | ✗ |

**Bold ✓** = first solve by any Qwen experiment (E12 exclusive or E12+Opus only).

## Setup

**Hard subset definition.** The 45 tasks are those labeled "1–4 hours" (42 tasks) or ">4 hours" (3 tasks) by the SWE-bench Verified difficulty annotation. These represent the top 9% of the 500-task benchmark by estimated human fix time.

**Claude Opus 4.6.** Single attempt per task, 100 max LLM steps, temperature 0.6, max_tokens 16384. Prompt caching enabled (system prompt + tools + conversation history). Cache hit rate ~97%.

**Qwen3.5-35B-A3B.** Self-hosted on 8×H100 via vLLM. All use temperature 0.6, max_tokens 32768.
- **E8**: ACI workflow prompt, 200 steps, auto-compaction at 75% context.
- **E9**: ACI workflow prompt, 100 steps, compaction. Tighter step budget forces more efficient tool use.
- **E11v2**: Simplified prompt v2 — no explicit workflow, verify script required before TASK_COMPLETE, "TASK_COMPLETE as plain text" instruction, generic solutions preferred.
- **E12**: E11v2 prompt + `--edit-nudge` — after each successful `file_edit`, a user message is injected forcing the agent to immediately verify the change by running an inline `python -c` or /tmp test script before moving on.

**Evaluation.** Docker-based using the official `swebench` package. Test patches are stripped; only source-code changes are submitted. Each instance runs in an isolated container with pre-built environment images.

---

*Updated 2026-03-04 · [agent-verify](https://github.com/SeungyounShin/agent-verify)*
