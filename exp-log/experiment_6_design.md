# Experiment 6: Enhanced Agent-Computer Interface (ACI)

## Motivation

Experiments 2–5 focused on **scaling** (more tokens, more steps, compaction) to improve resolve rate from 17.4% → 34.8%. However, SWE-agent research shows that the **tool interface design** itself can have a 15–20%p impact — even larger than model scaling. Claude Code's toolset offers further evidence: structured tools (grep, glob, lint-gated edit) reduce wasted steps and prevent cascading errors.

Analysis of our persistent failures (pvlib, pydicom, astroid-1978) revealed:
- Agent wastes steps using `bash grep` / `bash find` instead of structured search
- Edit errors (syntax/indentation) go undetected, leading to broken patches
- Agent reads entire large files instead of navigating to relevant sections
- Agent doesn't systematically run tests after edits
- Large bash output (test traces) floods context without adding signal

## Hypothesis

**Improving the tool interface will increase resolve rate more cost-effectively than further scaling.** Specifically:

1. **Lint-gated editing** prevents syntax errors from propagating → fewer wasted recovery steps
2. **Dedicated grep/glob tools** with structured output → faster code navigation, fewer bash-grep steps
3. **Windowed file reading** (200 lines + offset) → less context waste on large files
4. **Bash output truncation** (30K cap) → prevents test output from flooding context
5. **System prompt guidance** (read-before-edit, tool routing) → agent follows better workflow patterns

**Expected impact**: +2–4 tasks resolved (34.8% → 43–52%), with **lower** total token consumption.

## Experimental Design

### Independent Variable

Tool interface version:
- **Control (Exp 5)**: 4 tools — `file_read`, `file_write`, `file_edit`, `bash`
- **Treatment (Exp 6)**: 6 tools — enhanced `file_read`, enhanced `file_edit`, `file_write`, enhanced `bash`, `grep` (new), `glob` (new) + enhanced system prompt

### Changes Implemented

| Component | Before (Exp 5) | After (Exp 6) |
|-----------|-----------------|---------------|
| **file_read** | Returns raw content | Line numbers, windowed (200 lines, offset/limit), 2000 char/line truncation |
| **file_edit** | Simple string replace | + flake8 lint check (`E9,W6`), auto-rollback on syntax error |
| **bash** | Raw output | 30K char truncation, "no output" message, soft guidance against grep/find |
| **grep** (NEW) | N/A | ripgrep wrapper: regex, glob filter, context lines, 50 result cap |
| **glob** (NEW) | N/A | pathlib.glob wrapper: pattern matching, 200 file cap |
| **system prompt** | 1 sentence | Tool usage guidelines, read-before-edit rule, search strategy, test-after-edit workflow |

### Controlled Variables (same as Exp 5)

- **Benchmark**: SWE-bench Lite, dev split (23 tasks)
- **Model**: Qwen 3.5 397B (FP8 MoE), vLLM local, temperature=0.6
- **Context**: 131,072 tokens (128K), compaction threshold 75%
- **Steps**: max 2000
- **Timeout**: none
- **Task message**: includes workspace_dir + task_id
- **Parallelism**: 5 concurrent tasks

### Dependent Variables (metrics)

| Metric | How measured |
|--------|-------------|
| **Resolve rate** | Docker eval (gold tests), primary metric |
| **Total tokens** | Sum of input + output tokens across all tasks |
| **Avg steps per task** | Number of LLM calls before TASK_COMPLETE |
| **Lint rollback rate** | Count of file_edit calls that triggered rollback |
| **Tool usage distribution** | Counts of each tool call type |
| **Per-task comparison** | PASS/FAIL delta vs all previous experiments |

### Analysis Plan

1. **Primary**: resolve rate comparison vs Exp 5 (8/23 = 34.8%)
2. **Per-task delta**: which tasks flipped FAIL→PASS or PASS→FAIL?
3. **Tool usage**: did the agent actually use grep/glob? How often did lint-gating fire?
4. **Token efficiency**: tokens per resolved task (cost-effectiveness)
5. **Qualitative**: for tasks that flipped, what was the mechanism? (lint prevented bad edit? grep found right code faster?)

## Predictions

| Task category | Prediction | Reasoning |
|---------------|------------|-----------|
| Persistent PASS (marshmallow-1343, pydicom-1694, sqlfluff-2419) | Stay PASS | These are easy enough that tool changes won't affect |
| Recent PASS (marshmallow-1359, sqlfluff-1517, sqlfluff-1733, pydicom-1256, astroid-1196) | Stay PASS, possibly more robust | Better tools should make correct solutions easier to reach |
| Near-miss FAIL (astroid-1333, astroid-1866, pvlib-1072, astroid-1268) | Some may flip to PASS | These resolved in *some* experiments — better navigation could tip them |
| Hard FAIL (pvlib-1154/1606/1707/1854, pydicom-901/1139/1413, astroid-1978) | Likely stay FAIL | Require domain knowledge the model lacks; tools can't fix that |
| Variance-sensitive (sqlfluff-1625, sqlfluff-1763, pyvista-4315) | Unpredictable | These seem model-stochasticity-dependent |

**Conservative estimate**: 9–10/23 (39–43%)
**Optimistic estimate**: 11–12/23 (48–52%)

## Risks & Limitations

1. **ripgrep availability**: `rg` must be installed in the Docker workspace. If not, grep tool falls back gracefully with error message, but agent loses the benefit.
2. **flake8 availability**: lint-gating requires flake8. If absent, edits proceed without lint check (no regression).
3. **Stochasticity**: temperature=0.6 means single-run results have high variance. Ideally we'd run 3 trials, but cost is ~38M tokens × 3 = 114M tokens.
4. **System prompt length**: enhanced prompt is ~800 tokens vs ~50 tokens. This is negligible in a 128K context but worth noting.
5. **Confounded changes**: We're changing 6 things at once. If resolve rate improves, we can't attribute it to a single change. Ablation studies would require 6 separate runs.

## Execution Plan

```
1. Verify tools: python3 -c "from src.agent_verify.tools import create_default_toolset; ..."
2. Create config: configs/experiments/exp6_enhanced_aci.yaml
3. Run: python3 scripts/run_compaction_experiment.py --config configs/experiments/exp6_enhanced_aci.yaml
4. Docker eval: python3 scripts/docker_eval.py --predictions results/exp6/...
5. Analyze: compare per-task results, tool usage stats, token consumption
6. Update exp-log/EXPERIMENTS.md with results
```
