# SWE-bench Verified Hard — Model Comparison

**45 tasks rated 1–4 hours or >4 hours fix time · March 2026**

## Summary

| Metric | Claude Opus 4.6 | Qwen E11v2 (prompt v2) | Qwen E9 (100 steps) | Qwen E8 (200 steps) |
|--------|----------------:|-----------------------:|---------------------:|---------------------:|
| Resolved | **18/45 (40.0%)** | 15/45 (33.3%) | 10/45 (22.2%) | 8/45 (17.8%) |
| Agent completed | 39/45 (86.7%) | 30/45 (66.7%) | — | — |
| Has patch | 44/45 (97.8%) | — | — | — |
| Total cost | $62.29 | $0 (local) | $0 (local) | $0 (local) |
| Avg cost/task | $1.38 | — | — | — |
| Exclusive solves | **3** | 2 | 0 | 0 |
| Union (Opus + E11v2) | **23/45 (51.1%)** | | | |
| Union (all models) | 23/45 (51.1%) | | | |

> Prompt v2 (E11v2) closes the gap with Opus: **15/45 (33.3%)** vs Opus **18/45 (40.0%)**, and contributes **5 solves Opus missed** (django-13344, django-14011, django-16263, sphinx-11510, sympy-13852). The union of E11v2 + Opus reaches **23/45 (51.1%)**.

## Per-Repository Breakdown

| Repository | Tasks | Opus | E11v2 | Qwen E9 | Qwen E8 |
|------------|------:|-----:|------:|--------:|--------:|
| django/django | 22 | **10** | 9 | 5 | 4 |
| sympy/sympy | 7 | 2 | **3** | 0 | 1 |
| sphinx-doc/sphinx | 5 | 1 | **1** | 0 | 0 |
| astropy/astropy | 3 | 1 | **1** | 1 | 1 |
| pydata/xarray | 2 | **1** | 0 | 0 | 0 |
| pytest-dev/pytest | 3 | **1** | 0 | 1 | 1 |
| scikit-learn | 1 | **1** | 0 | 0 | 1 |
| pylint-dev/pylint | 2 | 0 | 0 | 0 | 0 |

## Per-Task Results

| Task ID | Difficulty | Opus | E11v2 | E9 | E8 |
|---------|-----------|:----:|:-----:|:--:|:--:|
| `astropy__astropy-13398` | >4h | ✗ | ✗ | ✗ | ✗ |
| `astropy__astropy-13579` | 1-4h | ✓ | ✓ | ✓ | ✓ |
| `astropy__astropy-14369` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `django__django-10554` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `django__django-11138` | 1-4h | ✓ | ✗ | ✓ | ✗ |
| `django__django-11400` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `django__django-11885` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `django__django-12325` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `django__django-12708` | 1-4h | ✓ | ✓ | ✓ | ✓ |
| `django__django-13128` | 1-4h | ✓ | ✓ | ✓ | ✗ |
| `django__django-13212` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `django__django-13344` | 1-4h | ✗ | ✓ | ✗ | ✗ |
| `django__django-13449` | 1-4h | ✓ | ✓ | ✓ | ✗ |
| `django__django-13837` | 1-4h | ✓ | ✓ | ✓ | ✗ |
| `django__django-14007` | 1-4h | ✓ | ✓ | ✓ | ✓ |
| `django__django-14011` | >4h | ✗ | ✓ | ✗ | ✗ |
| `django__django-14631` | 1-4h | ✓ | ✓ | ✓ | ✓ |
| `django__django-15128` | 1-4h | ✓ | ✓ | ✗ | ✗ |
| `django__django-15268` | 1-4h | ✓ | ✗ | ✓ | ✓ |
| `django__django-15503` | 1-4h | ✓ | ✗ | ✗ | ✗ |
| `django__django-15629` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `django__django-15957` | 1-4h | ✓ | ✗ | ✗ | ✗ |
| `django__django-16263` | 1-4h | ✗ | ✓ | ✗ | ✗ |
| `django__django-16560` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `django__django-16631` | >4h | ✗ | ✗ | ✗ | ✗ |
| `pydata__xarray-3993` | 1-4h | ✓ | ✗ | ✗ | ✗ |
| `pydata__xarray-6992` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `pylint-dev__pylint-4551` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `pylint-dev__pylint-8898` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `pytest-dev__pytest-10356` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `pytest-dev__pytest-5787` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `pytest-dev__pytest-6197` | 1-4h | ✓ | ✗ | ✓ | ✓ |
| `scikit-learn__scikit-learn-25102` | 1-4h | ✓ | ✗ | ✗ | ✓ |
| `sphinx-doc__sphinx-11510` | 1-4h | ✗ | ✓ | ✗ | ✗ |
| `sphinx-doc__sphinx-7590` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `sphinx-doc__sphinx-8548` | 1-4h | ✓ | ✗ | ✗ | ✗ |
| `sphinx-doc__sphinx-9229` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `sphinx-doc__sphinx-9461` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `sympy__sympy-12489` | 1-4h | ✓ | ✓ | ✗ | ✓ |
| `sympy__sympy-13852` | 1-4h | ✗ | ✓ | ✗ | ✗ |
| `sympy__sympy-13878` | 1-4h | ✓ | ✓ | ✗ | ✗ |
| `sympy__sympy-14248` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `sympy__sympy-16597` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `sympy__sympy-17630` | 1-4h | ✗ | ✗ | ✗ | ✗ |
| `sympy__sympy-18199` | 1-4h | ✗ | ✗ | ✗ | ✗ |

## Setup

**Hard subset definition.** The 45 tasks are those labeled "1–4 hours" (42 tasks) or ">4 hours" (3 tasks) by the SWE-bench Verified difficulty annotation. These represent the top 9% of the 500-task benchmark by estimated human fix time.

**Claude Opus 4.6.** Single attempt per task, 100 max LLM steps, temperature 0.6, max_tokens 16384. Prompt caching enabled (system prompt + tools + conversation history). Cache hit rate ~97%.

**Qwen3.5-35B-A3B.** Self-hosted on 8×H100 via vLLM. E8: 200 steps with auto-compaction at 75% context. E9: 100 steps with compaction. E11v2: 200 steps with simplified prompt v2 (no explicit workflow, verify script required, TASK_COMPLETE as plain text). All use temperature 0.6, max_tokens 32768.

**Evaluation.** Docker-based using the official `swebench` package. Test patches are stripped; only source-code changes are submitted. Each instance runs in an isolated container with pre-built environment images.

---

*Generated 2026-03-02 · [agent-verify](https://github.com/robin/agent-verify)*
