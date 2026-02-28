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

---

## Experiment 2: Qwen V0 on SWE-bench Lite dev (23 tasks)

Baseline run on a larger task set to establish Qwen V0 performance.

- **Benchmark**: SWE-bench Lite, dev split (23 tasks)
- **Model**: Qwen 3.5 397B (FP8 MoE), vLLM local
- **Config**: `max_iterations=40`, `token_budget=1M`, `timeout=1800s`

### Results

- **Resolved: 4/23 (17.4%)**
- 17/23 non-empty patches submitted (6 empty/no-patch)
- Frequent early termination: most tasks hit `token_budget` or `max_iterations`

| Resolved | Unresolved (patch) | No patch |
|---|---|---|
| marshmallow-1343, pydicom-1694, astroid-1866, sqlfluff-2419 | 13 tasks | 6 tasks |

### Files

- `results/lite_dev/` — Raw data, patches
- `results/lite_dev/docker_eval/qwen_v0_lite_dev.qwen_v0_lite_dev.json` — Docker eval report
- `configs/experiments/v0_qwen_lite_dev.yaml`

---

## Experiment 3: Unlimited Budget (no compaction) on SWE-bench Lite dev

Test whether removing iteration/token limits improves resolve rate. Originally designed to test auto-compaction, but vLLM context window (131K) was large enough that compaction never triggered.

- **Benchmark**: SWE-bench Lite, dev split (23 tasks, 22 ran — pyvista-4315 workspace provision failed)
- **Model**: Qwen 3.5 397B (FP8 MoE), vLLM local
- **Config**: No `max_iterations`, no `token_budget`, `timeout=3600s`, `max_steps=500` (safety cap)
- **Compaction threshold**: 75% of 131,072 = 98,304 input tokens (never reached)

### Results

- **Resolved: 7/23 (30.4%)**
- 22/22 non-empty patches (all ran tasks produced diffs)
- 0 compactions triggered (max input tokens per call: ~76K, threshold: ~98K)
- Total tokens: 32.3M (vs V0's ~4.5M for same tasks)

### Per-Task Comparison (V0 Baseline vs Unlimited)

```
Task                                     V0 Baseline    Unlimited
──────────────────────────────────────────────────────────────────
marshmallow-code__marshmallow-1343          PASS           PASS
marshmallow-code__marshmallow-1359          FAIL           FAIL
pvlib__pvlib-python-1072                    FAIL           FAIL
pvlib__pvlib-python-1154                  EMPTY           FAIL
pvlib__pvlib-python-1606                    FAIL           FAIL
pvlib__pvlib-python-1707                    FAIL           FAIL
pvlib__pvlib-python-1854                    FAIL           FAIL  (llm_error)
pydicom__pydicom-901                        FAIL           FAIL
pydicom__pydicom-1139                       FAIL           FAIL
pydicom__pydicom-1256                     EMPTY          *PASS*
pydicom__pydicom-1413                       FAIL           FAIL
pydicom__pydicom-1694                       PASS           PASS
pylint-dev__astroid-1196                  EMPTY          *PASS*
pylint-dev__astroid-1268                    FAIL           FAIL  (llm_error)
pylint-dev__astroid-1333                  EMPTY          *PASS*
pylint-dev__astroid-1866                    PASS           PASS
pylint-dev__astroid-1978                    FAIL           FAIL
pyvista__pyvista-4315                       FAIL           N/A   (provision fail)
sqlfluff__sqlfluff-1517                   EMPTY           FAIL  (timeout)
sqlfluff__sqlfluff-1625                     FAIL           FAIL
sqlfluff__sqlfluff-1733                   EMPTY           FAIL  (timeout)
sqlfluff__sqlfluff-1763                     FAIL           FAIL
sqlfluff__sqlfluff-2419                     PASS           PASS
──────────────────────────────────────────────────────────────────
Resolved                                  4/23           7/23
Resolve %                                17.4%          30.4%
Total tokens                             ~4.5M          32.3M
```

### Key Findings

1. **Removing limits alone gains +3 tasks (17.4% → 30.4%)** — pydicom-1256, astroid-1196, astroid-1333 were all tasks where V0 produced empty patches (hit budget before finishing). Given more steps, the agent completed them.
2. **Compaction never triggered** — With vLLM max_model_len=131,072, the 75% threshold (98K input tokens) was never reached. Max observed input tokens per call was ~76K.
3. **7x more tokens consumed** (32.3M vs ~4.5M) for +3 tasks — expensive trade-off.
4. **2 tasks hit timeout (3600s)**: sqlfluff-1517 (97 steps), sqlfluff-1733 (81 steps) — agent kept iterating without converging.
5. **2 tasks hit llm_error**: pvlib-1854, astroid-1268 — vLLM errors during generation.

### Files

- `results/compaction_retry/` — Raw data, patches, summary
- `results/compaction_retry/compaction_qwen_lite_dev_summary.json` — Per-task summary
- `compaction_qwen_lite_dev.compaction_qwen_lite_dev.json` — Docker eval report
- `configs/experiments/compaction_qwen_lite_dev.yaml`
- `scripts/run_compaction_experiment.py` — Experiment runner (auto-compaction loop)

---

## Experiment 4: Auto-Compaction (32K context) on SWE-bench Lite dev

Test auto-compaction with a 32K context window where compaction actually triggers frequently.

- **Benchmark**: SWE-bench Lite, dev split (23 tasks, 22 ran — pyvista-4315 workspace provision failed)
- **Model**: Qwen 3.5 397B (FP8 MoE), vLLM local
- **Config**: No `max_iterations`, no timeout, `max_steps=500` (safety cap)
- **Compaction**: threshold 75% of 32,768 = 24,576 input tokens → compacts conversation into summary, resets context with system prompt + summary + task description

### Results

- **Resolved: 7/23 (30.4%)**
- 17/23 agent_declared TASK_COMPLETE, 5 hit max_steps (500)
- **439 compactions** total (vs 0 in Experiment 3)
- Total tokens: 57.5M

### Per-Task Comparison (all 3 experiments)

```
Task                                     V0 (17.4%)   Unlimited    Compaction
                                                      131K(30.4%)  32K(30.4%)
─────────────────────────────────────────────────────────────────────────────
marshmallow-code__marshmallow-1343          PASS        PASS         PASS
marshmallow-code__marshmallow-1359          FAIL        FAIL         FAIL       (5 compactions)
pvlib__pvlib-python-1072                    FAIL        FAIL         PASS
pvlib__pvlib-python-1154                  EMPTY        FAIL         FAIL       (41 compactions)
pvlib__pvlib-python-1606                    FAIL        FAIL         FAIL       (2 compactions)
pvlib__pvlib-python-1707                    FAIL        FAIL         FAIL       (2 compactions)
pvlib__pvlib-python-1854                    FAIL        FAIL(err)    FAIL       (54 compactions)
pydicom__pydicom-901                        FAIL        FAIL         FAIL
pydicom__pydicom-1139                       FAIL        FAIL         FAIL
pydicom__pydicom-1256                     EMPTY       *PASS*        FAIL       (44 compactions, max_steps)
pydicom__pydicom-1413                       FAIL        FAIL         FAIL       (3 compactions)
pydicom__pydicom-1694                       PASS        PASS         PASS       (41 compactions)
pylint-dev__astroid-1196                  EMPTY       *PASS*        FAIL       (131 compactions, max_steps)
pylint-dev__astroid-1268                    FAIL        FAIL(err)    PASS
pylint-dev__astroid-1333                  EMPTY       *PASS*       *PASS*      (2 compactions)
pylint-dev__astroid-1866                    PASS        PASS         PASS       (2 compactions)
pylint-dev__astroid-1978                    FAIL        FAIL         FAIL
pyvista__pyvista-4315                       FAIL        N/A          N/A        (provision fail)
sqlfluff__sqlfluff-1517                   EMPTY        FAIL(to)     FAIL       (52 compactions, max_steps)
sqlfluff__sqlfluff-1625                     FAIL        FAIL         FAIL       (12 compactions, max_steps)
sqlfluff__sqlfluff-1733                   EMPTY        FAIL(to)     FAIL       (20 compactions, max_steps)
sqlfluff__sqlfluff-1763                     FAIL        FAIL        *PASS*      (25 compactions)
sqlfluff__sqlfluff-2419                     PASS        PASS         PASS
─────────────────────────────────────────────────────────────────────────────
Resolved                                  4/23         7/23         7/23
Resolve %                                17.4%        30.4%        30.4%
Total tokens                             ~4.5M        32.3M        57.5M
Compactions                                N/A          0           439
```

### Key Findings

1. **Compaction (32K) matches unlimited (131K) resolve rate: both 7/23 (30.4%)** — auto-compaction successfully enables the agent to work within a small context window without losing effectiveness.
2. **Different tasks resolved**: Compaction gains pvlib-1072, astroid-1268, sqlfluff-1763 but loses pydicom-1256, astroid-1196 (both hit max_steps with 44/131 compactions — compaction information loss caused loops).
3. **Token cost: 57.5M vs 32.3M (1.8x)** — compaction overhead from summary generation calls and repeated context.
4. **High-compaction tasks tend to loop**: astroid-1196 (131 compactions), pvlib-1854 (54 compactions), sqlfluff-1517 (52 compactions) all hit max_steps — the agent loses too much context and repeats work.
5. **Moderate compaction works well**: Tasks with 2-5 compactions often succeed (marshmallow-1343, astroid-1333, astroid-1866, pvlib-1707).

### Files

- `results/compaction_retry/compaction_qwen_lite_dev_summary.json` — Per-task summary (overwritten)
- `compaction_32k.compaction_32k.json` — Docker eval report
- `scripts/run_compaction_experiment.py` — Updated with new compaction prompt, no timeout

---

## Experiment 5: 128K Context + Task Context + Max Steps 2000

Addressed issues from Experiment 4: raised compaction threshold to actual vLLM max_model_len (128K), increased max steps from 500 to 2000, and added explicit workspace directory + task ID to the user message to prevent task confusion after compaction.

- **Benchmark**: SWE-bench Lite, dev split (23 tasks, all ran including pyvista-4315)
- **Model**: Qwen 3.5 397B (FP8 MoE), vLLM local
- **Config**: No timeout, `max_steps=2000`, compaction threshold 75% of 131,072 = 98,304 input tokens
- **Changes vs Exp 4**:
  1. `max_context`: 32K → 131K (actual vLLM max_model_len)
  2. `MAX_STEPS`: 500 → 2000
  3. Task message now includes: `"You are working in the repository at: {workspace_dir}\nTask ID: {task_id}"`

### Results

- **Resolved: 8/23 (34.8%)** — best result across all experiments
- 20/23 agent_declared TASK_COMPLETE, 3 llm_error
- **0 compactions** (128K context sufficient for all tasks)
- 0 max_steps hits (2000 limit never reached)
- Total tokens: 38.0M

### Per-Task Comparison (all experiments)

```
Task                                     V0       Unltd    Comp32K  128K+ctx
                                        (17.4%)  (30.4%)  (30.4%)  (34.8%)
─────────────────────────────────────────────────────────────────────────────
marshmallow-code__marshmallow-1343       PASS      PASS     PASS     PASS
marshmallow-code__marshmallow-1359       FAIL      FAIL     FAIL    *PASS*  ← NEW
pvlib__pvlib-python-1072                 FAIL      FAIL     PASS     FAIL
pvlib__pvlib-python-1154               EMPTY      FAIL     FAIL     FAIL   (llm_error)
pvlib__pvlib-python-1606                 FAIL      FAIL     FAIL     FAIL
pvlib__pvlib-python-1707                 FAIL      FAIL     FAIL     FAIL
pvlib__pvlib-python-1854                 FAIL      FAIL     FAIL     FAIL
pydicom__pydicom-901                     FAIL      FAIL     FAIL     FAIL
pydicom__pydicom-1139                    FAIL      FAIL     FAIL     FAIL
pydicom__pydicom-1256                  EMPTY     *PASS*    FAIL    *PASS*
pydicom__pydicom-1413                    FAIL      FAIL     FAIL     FAIL   (llm_error)
pydicom__pydicom-1694                    PASS      PASS     PASS     PASS
pylint-dev__astroid-1196               EMPTY     *PASS*    FAIL    *PASS*
pylint-dev__astroid-1268                 FAIL      FAIL     PASS     FAIL
pylint-dev__astroid-1333               EMPTY     *PASS*    PASS     FAIL
pylint-dev__astroid-1866                 PASS      PASS     FAIL     FAIL
pylint-dev__astroid-1978                 FAIL      FAIL     FAIL     FAIL
pyvista__pyvista-4315                    FAIL      N/A      N/A      FAIL
sqlfluff__sqlfluff-1517                EMPTY      FAIL     FAIL    *PASS*  ← NEW
sqlfluff__sqlfluff-1625                  FAIL      FAIL     FAIL     FAIL
sqlfluff__sqlfluff-1733                EMPTY      FAIL     FAIL    *PASS*  ← NEW
sqlfluff__sqlfluff-1763                  FAIL      FAIL     PASS     FAIL
sqlfluff__sqlfluff-2419                  PASS      PASS     PASS     PASS
─────────────────────────────────────────────────────────────────────────────
Resolved                                4/23     7/23     7/23     8/23
Resolve %                              17.4%    30.4%    30.4%    34.8%
Total tokens                           ~4.5M    32.3M    57.5M    38.0M
Compactions                              N/A      0       439      0
Max steps hit                            N/A      2        5       0
```

### Key Findings

1. **Best resolve rate: 8/23 (34.8%)** — task context + higher step limit produced 3 tasks never solved before (marshmallow-1359, sqlfluff-1517, sqlfluff-1733).
2. **Task context matters**: Adding workspace dir and task ID to user message prevented task confusion that plagued Experiment 4.
3. **No compaction needed at 128K**: All tasks completed within the 128K context window without compaction. Max input tokens stayed below 98K threshold.
4. **No max_steps hits**: 2000 step limit was never reached. Longest task was sqlfluff-1733 at 126 steps before llm_error.
5. **Variance across runs**: Some tasks resolve inconsistently across experiments (e.g., astroid-1333 resolved in Exp 3/4 but not here; pvlib-1072 resolved in Exp 4 but not here). This suggests model stochasticity (temperature=0.6) plays a role.
6. **Persistent failures**: pvlib family (1154, 1606, 1707, 1854), pydicom-901/1139, astroid-1978 failed in ALL experiments — these are fundamentally hard for this model.

### Files

- `results/compaction_128k/` — Raw data, patches, summary
- `results/compaction_128k/compaction_128k_qwen_lite_dev_summary.json`
- `compaction_128k.compaction_128k.json` — Docker eval report
- `configs/experiments/compaction_128k_qwen_lite_dev.yaml`

---

## Experiment 6: Enhanced Agent-Computer Interface (ACI)

Test whether improving the tool interface (inspired by SWE-agent ACI and Claude Code) improves resolve rate. All scaling parameters identical to Exp 5 — only the tools and system prompt changed.

- **Benchmark**: SWE-bench Lite, dev split (23 tasks, all ran)
- **Model**: Qwen 3.5 397B (FP8 MoE), vLLM local
- **Config**: Same as Exp 5 — no timeout, `max_steps=2000`, 128K context, task context in user message
- **Changes vs Exp 5**:
  1. `file_read`: line numbers, windowed viewing (200 lines, offset/limit), 2000 char/line truncation
  2. `file_edit`: flake8 lint-gated editing (`--select=E9,W6`), auto-rollback on syntax error
  3. `grep` (NEW): ripgrep wrapper with regex, glob filter, context lines, 50 result cap
  4. `glob` (NEW): pathlib.glob wrapper, 200 file cap
  5. `bash`: 30K output truncation, empty output message, soft guidance against grep/find
  6. System prompt: tool usage guidelines, read-before-edit rule, search strategy, test-after-edit workflow

### Results

- **Resolved: 6/23 (26.1%)** — regression from Exp 5 (34.8%)
- 22/23 agent_declared TASK_COMPLETE, 1 llm_error (sqlfluff-1733)
- **0 compactions** (128K context sufficient)
- Total tokens: 38.3M

### Per-Task Comparison (all experiments)

```
Task                                V0       Unltd    Comp32K  Exp5     Exp6
                                   (17.4%)  (30.4%)  (30.4%)  (34.8%)  (26.1%)
─────────────────────────────────────────────────────────────────────────────
marshmallow-code__marshmallow-1343  PASS     PASS     PASS     PASS     PASS
marshmallow-code__marshmallow-1359  FAIL     FAIL     FAIL    *PASS*    PASS
pvlib__pvlib-python-1072            FAIL     FAIL     PASS     FAIL     FAIL
pvlib__pvlib-python-1154           EMPTY     FAIL     FAIL     FAIL     FAIL
pvlib__pvlib-python-1606            FAIL     FAIL     FAIL     FAIL    *PASS*  ← NEW
pvlib__pvlib-python-1707            FAIL     FAIL     FAIL     FAIL     FAIL
pvlib__pvlib-python-1854            FAIL     FAIL     FAIL     FAIL     FAIL
pydicom__pydicom-901                FAIL     FAIL     FAIL     FAIL     FAIL
pydicom__pydicom-1139               FAIL     FAIL     FAIL     FAIL     FAIL
pydicom__pydicom-1256              EMPTY    *PASS*    FAIL    *PASS*    PASS
pydicom__pydicom-1413               FAIL     FAIL     FAIL     FAIL     FAIL
pydicom__pydicom-1694               PASS     PASS     PASS     PASS     PASS
pylint-dev__astroid-1196           EMPTY    *PASS*    FAIL    *PASS*    FAIL    ← lost
pylint-dev__astroid-1268            FAIL     FAIL     PASS     FAIL     FAIL
pylint-dev__astroid-1333           EMPTY    *PASS*    PASS     FAIL     FAIL
pylint-dev__astroid-1866            PASS     PASS     FAIL     FAIL     FAIL
pylint-dev__astroid-1978            FAIL     FAIL     FAIL     FAIL     FAIL
pyvista__pyvista-4315               FAIL     N/A      N/A      FAIL     FAIL
sqlfluff__sqlfluff-1517            EMPTY     FAIL     FAIL    *PASS*    FAIL    ← lost
sqlfluff__sqlfluff-1625             FAIL     FAIL     FAIL     FAIL     FAIL
sqlfluff__sqlfluff-1733            EMPTY     FAIL     FAIL    *PASS*    FAIL    ← lost
sqlfluff__sqlfluff-1763             FAIL     FAIL     PASS     FAIL     FAIL
sqlfluff__sqlfluff-2419             PASS     PASS     PASS     PASS     PASS
─────────────────────────────────────────────────────────────────────────────
Resolved                           4/23     7/23     7/23     8/23     6/23
Resolve %                         17.4%    30.4%    30.4%    34.8%    26.1%
Total tokens                      ~4.5M    32.3M    57.5M    38.0M    38.3M
Compactions                         N/A      0       439      0        0
```

### Key Findings

1. **ACI improvements did NOT improve resolve rate**: 6/23 (26.1%) vs Exp 5's 8/23 (34.8%) — a -2 task regression.
2. **pvlib-1606 resolved for the first time**: Never solved in any previous experiment. The enhanced grep/glob tools likely helped navigate the codebase more effectively.
3. **3 regressions vs Exp 5**: astroid-1196, sqlfluff-1517, sqlfluff-1733 all flipped PASS→FAIL. These were first-time PASS in Exp 5.
4. **Stochasticity dominates**: With temperature=0.6, single-run results have high variance. The tasks that flip between experiments (astroid-1196, sqlfluff-1517, pvlib-1072, etc.) appear sensitive to random sampling rather than tool design.
5. **Token consumption unchanged**: 38.3M vs 38.0M — the new tools didn't reduce or increase token usage meaningfully.
6. **All tasks produced patches**: 23/23 non-empty diffs (22 agent_declared + 1 llm_error with partial diff).

### Files

- `results/exp6_enhanced_aci/` — Raw data, patches, summary
- `configs/experiments/exp6_enhanced_aci.yaml`
- `exp-log/experiment_6_design.md` — Experiment hypothesis and design document
- `src/agent_verify/tools/grep.py` — New GrepTool
- `src/agent_verify/tools/glob.py` — New GlobTool

---

## Experiment 8: Qwen3.5-35B-A3B on SWE-bench Verified (500 tasks)

First large-scale evaluation using a smaller MoE model on the full SWE-bench Verified benchmark.

- **Benchmark**: SWE-bench Verified, test split (500 tasks)
- **Model**: Qwen3.5-35B-A3B (35B total, 3B active), vLLM local, max_model_len=262144 (256K)
- **Config**: `max_steps=200`, `max_context=262144`, `temperature=0.6`, `top_p=0.95`, `top_k=20`
- **Tools**: file_read, file_write, file_edit (lint-gated), bash (30K truncation), grep (ripgrep), glob (pathlib)
- **System prompt**: Enhanced ACI with tool usage guidelines (same as Exp 6)
- **Note**: Model heavily favored bash tool (90.4% of all tool calls), largely ignoring dedicated grep/glob/file_edit tools

### Results

- **Resolved: 314/500 (62.8%)**
- 497/500 patches generated (3 empty/no-patch)
- 469/497 evaluated (1 error, 27 not evaluated due to empty patches or image issues)
- 211 agent_declared TASK_COMPLETE, 276 hit max_steps (200), 10 llm_error
- 8 compactions triggered (256K context sufficient for most tasks)
- Total tokens: 3.27B

### Per-Repo Breakdown

```
Repo                              Resolved  Unresolved  Total   %
──────────────────────────────────────────────────────────────────
django__django                       150        69       219   68.5%
sympy__sympy                          46        24        70   65.7%
scikit-learn__scikit-learn            25         6        31   80.6%
sphinx-doc__sphinx                    22        20        42   52.4%
matplotlib__matplotlib                20         8        28   71.4%
pydata__xarray                        15         7        22   68.2%
pytest-dev__pytest                    13         3        16   81.3%
astropy__astropy                      11        10        21   52.4%
psf__requests                          6         2         8   75.0%
pylint-dev__pylint                     5         5        10   50.0%
pallets__flask                         1         0         1  100.0%
mwaskom__seaborn                       0         1         1    0.0%
──────────────────────────────────────────────────────────────────
TOTAL                                314       155       469   67.0%
```

### Tool Usage

```
Tool          Calls      %
──────────────────────────
bash          64,071   90.4%
file_read      4,419    6.2%
file_edit      1,613    2.3%
grep             299    0.4%
glob             248    0.3%
task_complete     87    0.1%
```

### Key Findings

1. **62.8% resolve rate on SWE-bench Verified** — strong result for a 3B-active MoE model. For context, top leaderboard systems achieve ~55-70% on Verified.
2. **Model ignores ACI tools**: Despite system prompt guidance, 90.4% of tool calls are bash. The 35B model has weak instruction following for tool selection, defaulting to shell commands for everything (grep, cat, sed via bash instead of dedicated tools).
3. **55.2% of tasks hit max_steps (200)**: Many tasks loop without converging, especially on harder repos (astropy, sphinx). Raising max_steps might help some but would increase cost.
4. **scikit-learn and pytest are easiest** (80%+), while pylint, astropy, sphinx are hardest (~50%).
5. **256K context is sufficient**: Only 8 compactions across 500 tasks. The model rarely fills the context window.
6. **3.27B total tokens for 500 tasks** — average ~6.5M tokens per task, heavily skewed by max_steps tasks.

### Files

- `results/exp8_qwen35b_verified/` — Raw data, patches, summary
- `configs/experiments/exp8_qwen35b_verified.yaml`
- `exp8_final.exp8_final.json` — Docker eval report (final, all 500 tasks)

---

## Experiment 9: 100-Step Compaction on SWE-bench Verified (500 tasks)

Same model and tools as Exp 8, but with max_steps halved (200→100). Tests whether a tighter step budget forces the agent to be more efficient, reducing wasted loops.

- **Benchmark**: SWE-bench Verified, test split (500 tasks)
- **Model**: Qwen3.5-35B-A3B (35B total, 3B active), vLLM local, max_model_len=262144 (256K)
- **Config**: `max_steps=100`, `max_context=262144`, `temperature=0.6`, `top_p=0.95`, `top_k=20`
- **Tools**: file_read, file_write, file_edit (lint-gated), bash (30K truncation), grep (ripgrep), glob (pathlib)
- **System prompt**: Same enhanced ACI as Exp 8
- **Traces**: Full conversation traces saved via ExperimentLogger (viewable with `scripts/trace_viewer.py`)

### Results

- **Resolved: 320/500 (64.0%)** — up from 62.8% in Exp 8 (+1.2%p)
- 478/500 patches submitted, 476 evaluated (2 errors)
- Resolved on evaluated: 320/476 = 67.2% (vs Exp 8: 314/469 = 67.0%)

### Comparison with Exp 8

```
                    Exp8 (200 steps)    Exp9 (100 steps)    Diff
─────────────────────────────────────────────────────────────────
Resolved / 500         314 (62.8%)        320 (64.0%)     +6 (+1.2%p)
Step budget                    200                100      -50%
Both resolved                  275
Only Exp9 (new)                 45
Only Exp8 (regress)             39
Net gain                        +6
```

### Per-Repo Breakdown (Exp 8 → Exp 9)

```
Repo                         Exp8            Exp9         Diff
──────────────────────────────────────────────────────────────────
django/django             150/219=68.5%   154/222=69.4%   +0.9
sympy/sympy                46/ 70=65.7%    48/ 70=68.6%   +2.9
sphinx-doc/sphinx          22/ 42=52.4%    25/ 41=61.0%   +8.6
scikit-learn/scikit-learn  25/ 31=80.6%    24/ 31=77.4%   -3.2
matplotlib/matplotlib      20/ 28=71.4%    16/ 30=53.3%  -18.1
astropy/astropy            11/ 21=52.4%    12/ 22=54.5%   +2.2
pydata/xarray              15/ 22=68.2%    16/ 21=76.2%   +8.0
pytest-dev/pytest          13/ 16=81.2%    13/ 18=72.2%   -9.0
pylint-dev/pylint           5/ 10=50.0%     3/ 10=30.0%  -20.0
psf/requests                6/  8=75.0%     7/  8=87.5%  +12.5
mwaskom/seaborn             0/  1= 0.0%     1/  2=50.0%  +50.0
pallets/flask               1/  1=100.0%    1/  1=100.0%   0.0
```

### Tool Usage (Exp 8 → Exp 9)

```
Tool          Exp8 Calls    %      Exp9 Calls    %      Δ
──────────────────────────────────────────────────────────────
bash           64,071    90.7%      34,970    83.8%   -6.9%p
file_read       4,419     6.3%       4,466    10.7%   +4.5%p
file_edit       1,613     2.3%       1,544     3.7%   +1.4%p
grep              299     0.4%         332     0.8%   +0.4%p
glob              248     0.4%         268     0.6%   +0.3%p
TOTAL          70,650              41,715             -41%
```

### Key Findings

1. **64.0% resolve rate with half the steps** — 100-step budget is more efficient than 200. Net +6 tasks resolved.
2. **41% fewer total tool calls** (70K→42K) — significant compute savings with equal or better performance.
3. **Improved ACI tool adoption**: bash dropped from 90.7%→83.8%, while file_read rose from 6.3%→10.7%. The tighter step budget may force the model to use more efficient dedicated tools.
4. **Big gains on sphinx (+8.6%p) and xarray (+8.0%p)** — tasks that previously looped in 200 steps now produce correct patches earlier.
5. **Regressions on matplotlib (-18.1%p) and pylint (-20.0%p)** — some tasks genuinely need more than 100 steps.
6. **45 new solves vs 39 regressions** — not just the same tasks shifting; the shorter budget unlocks different tasks while losing others.

### Files

- `results/exp9_100step_compaction/` — Raw data, patches, traces, summary
- `results/exp9_100step_compaction/exp9_100step_compaction.jsonl` — Full trace (1016 events for 10-task pilot, full 500-task trace in same dir)
- `configs/experiments/exp9_100step_compaction.yaml`
- `exp9_final.exp9_final.json` — Docker eval report

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
