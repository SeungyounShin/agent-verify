"""Generate SWE-bench Verified Hard subset analysis figures."""
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor": "#161b22",
    "axes.edgecolor": "#30363d",
    "axes.labelcolor": "#c9d1d9",
    "text.color": "#c9d1d9",
    "xtick.color": "#8b949e",
    "ytick.color": "#8b949e",
    "grid.color": "#21262d",
    "font.family": "sans-serif",
    "font.size": 12,
    "figure.dpi": 150,
})

COLORS = {
    "Opus 4.6": "#a371f7",
    "E12 (edit-nudge)": "#3fb950",
    "E11 (verify script)": "#58a6ff",
    "E9 (100-step ACI)": "#f0883e",
    "E8 (200-step ACI)": "#8b949e",
}

OUT = Path("figures")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
def load_summary(path):
    return json.load(open(path))["per_task"]

opus_tasks = load_summary("results/hard_opus/hard_opus_summary.json")
e12_tasks = load_summary("results/exp12_hard45/exp12_hard45_summary.json")
e11_tasks = load_summary("results/exp11_hard45_v2/exp11_hard45_v2_summary.json")

# E9: filter to hard 45
hard_ids = {t["task_id"] for t in opus_tasks}
e9_all = load_summary("results/exp9_100step_compaction/exp9_100step_compaction_summary.json")
e9_tasks = [t for t in e9_all if t["task_id"] in hard_ids]

# E8: check if summary exists, else skip
try:
    e8_all = load_summary("results/exp8_qwen35b_verified/exp8_qwen35b_verified_summary.json")
    e8_tasks = [t for t in e8_all if t["task_id"] in hard_ids]
except FileNotFoundError:
    e8_tasks = None

# Resolved sets
opus_res = json.load(open("hard_opus.hard_opus.json"))["resolved_ids"]
e12_res = json.load(open("exp12_hard45_final.exp12_hard45_final.json"))["resolved_ids"]
e11_res = json.load(open("exp11_hard45_v2.exp11_hard45_v2.json"))["resolved_ids"]
e9_res_full = json.load(open("exp-log/docker_reports/exp9_final.exp9_final.json"))["resolved_ids"]
e9_res = [r for r in e9_res_full if r in hard_ids]

# E8 resolved
try:
    e8_res_full = json.load(open("exp-log/docker_reports/exp8_final.exp8_final.json"))["resolved_ids"]
    e8_res = [r for r in e8_res_full if r in hard_ids]
except FileNotFoundError:
    e8_res = []

# ---------------------------------------------------------------------------
# Fig 1: Resolution Bar Chart
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))

labels = ["Opus 4.6", "E12\n(edit-nudge)", "E11\n(verify script)", "E9\n(100-step ACI)", "E8\n(200-step ACI)"]
counts = [len(opus_res), len(e12_res), len(e11_res), len(e9_res), len(e8_res)]
colors = [COLORS[k] for k in COLORS]
total = 45

bars = ax.bar(labels, counts, color=colors, width=0.6, edgecolor="#30363d", linewidth=0.8)

for bar, c in zip(bars, counts):
    pct = c / total * 100
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
            f"{c}/45\n({pct:.1f}%)", ha="center", va="bottom",
            fontsize=11, fontweight="bold", color="#c9d1d9")

ax.set_ylabel("Resolved Tasks", fontsize=13)
ax.set_title("SWE-bench Verified Hard — Resolution by Strategy", fontsize=15, fontweight="bold", pad=15)
ax.set_ylim(0, max(counts) + 5)
ax.yaxis.set_major_locator(mticker.MultipleLocator(5))
ax.grid(axis="y", alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Union annotation
union_all = len(set(opus_res) | set(e12_res) | set(e11_res) | set(e9_res) | set(e8_res))
ax.annotate(f"Union (all) = {union_all}/45 ({union_all/45*100:.1f}%)",
            xy=(0.98, 0.95), xycoords="axes fraction", ha="right", va="top",
            fontsize=11, color="#f0883e",
            bbox=dict(boxstyle="round,pad=0.4", fc="#161b22", ec="#f0883e", alpha=0.9))

fig.tight_layout()
fig.savefig(OUT / "hard_resolution_bar.png", bbox_inches="tight")
print("Saved hard_resolution_bar.png")

# ---------------------------------------------------------------------------
# Fig 2: Cumulative Resolution vs Steps
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))

def cumulative_resolved(tasks, resolved_set, max_step=200):
    """For each step threshold, count how many resolved tasks completed within that step."""
    resolved_steps = []
    for t in tasks:
        if t["task_id"] in resolved_set:
            resolved_steps.append(t["total_steps"])
    steps_range = np.arange(1, max_step + 1)
    cum = [sum(1 for s in resolved_steps if s <= x) for x in steps_range]
    return steps_range, cum

configs = [
    ("Opus 4.6", opus_tasks, set(opus_res), 100),
    ("E12 (edit-nudge)", e12_tasks, set(e12_res), 200),
    ("E11 (verify script)", e11_tasks, set(e11_res), 200),
    ("E9 (100-step ACI)", e9_tasks, set(e9_res), 100),
]

for name, tasks, res, ms in configs:
    x, y = cumulative_resolved(tasks, res, ms)
    # Normalize to fraction
    y_frac = [v / 45 for v in y]
    ax.plot(x, y_frac, label=name, color=COLORS[name], linewidth=2.5, alpha=0.9)
    # Mark final value
    ax.scatter([x[-1]], [y_frac[-1]], color=COLORS[name], s=60, zorder=5)
    ax.annotate(f"{y[-1]}/45", xy=(x[-1], y_frac[-1]),
                xytext=(8, 0), textcoords="offset points",
                color=COLORS[name], fontsize=10, fontweight="bold", va="center")

ax.set_xlabel("Step Limit", fontsize=13)
ax.set_ylabel("Cumulative Resolve Rate", fontsize=13)
ax.set_title("Cumulative Resolution vs Steps (Hard Subset)", fontsize=15, fontweight="bold", pad=15)
ax.set_xlim(0, 210)
ax.set_ylim(0, 0.55)
ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
ax.grid(alpha=0.3)
ax.legend(loc="lower right", fontsize=10, framealpha=0.8,
          facecolor="#161b22", edgecolor="#30363d")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

fig.tight_layout()
fig.savefig(OUT / "hard_cumulative_steps.png", bbox_inches="tight")
print("Saved hard_cumulative_steps.png")

# ---------------------------------------------------------------------------
# Fig 3: Step Limit vs Performance (what-if analysis)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))

step_limits = [25, 50, 75, 100, 125, 150, 175, 200]

for name, tasks, res, _ in configs:
    perf = []
    for sl in step_limits:
        # Count resolved tasks that completed within this step limit
        count = sum(1 for t in tasks if t["task_id"] in res and t["total_steps"] <= sl)
        perf.append(count / 45 * 100)
    ax.plot(step_limits, perf, label=name, color=COLORS[name],
            linewidth=2.5, marker="o", markersize=6, alpha=0.9)

ax.set_xlabel("Max Steps Allowed", fontsize=13)
ax.set_ylabel("Resolve Rate (%)", fontsize=13)
ax.set_title("Step Limit vs Performance (Hard Subset)", fontsize=15, fontweight="bold", pad=15)
ax.set_xlim(20, 210)
ax.set_ylim(0, 50)
ax.grid(alpha=0.3)
ax.legend(loc="lower right", fontsize=10, framealpha=0.8,
          facecolor="#161b22", edgecolor="#30363d")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

fig.tight_layout()
fig.savefig(OUT / "hard_step_limit_perf.png", bbox_inches="tight")
print("Saved hard_step_limit_perf.png")

# ---------------------------------------------------------------------------
# Fig 4: Cost vs Performance Tradeoff
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))

# Compute costs
# Opus: actual cost from summary
opus_cost = sum(t.get("cost_usd", 0) for t in opus_tasks)

# Qwen: estimate from tokens. vLLM local = $0 API cost, but compute cost
# Use tokens as proxy. Compute total tokens per experiment.
def total_tokens(tasks):
    return sum(t["total_input_tokens"] + t["total_output_tokens"] for t in tasks)

e12_tok = total_tokens(e12_tasks) / 1e6
e11_tok = total_tokens(e11_tasks) / 1e6
e9_tok = total_tokens(e9_tasks) / 1e6

# Plot: x = total tokens (M), y = resolve rate, with Opus on secondary x-axis
# Use dual representation: tokens for Qwen, cost for Opus

resolve_rates = {
    "Opus 4.6": len(opus_res) / 45 * 100,
    "E12 (edit-nudge)": len(e12_res) / 45 * 100,
    "E11 (verify script)": len(e11_res) / 45 * 100,
    "E9 (100-step ACI)": len(e9_res) / 45 * 100,
}

token_costs = {
    "E12 (edit-nudge)": e12_tok,
    "E11 (verify script)": e11_tok,
    "E9 (100-step ACI)": e9_tok,
}

# Qwen points on token axis
for name in ["E9 (100-step ACI)", "E11 (verify script)", "E12 (edit-nudge)"]:
    ax.scatter(token_costs[name], resolve_rates[name],
               color=COLORS[name], s=200, zorder=5, edgecolors="#c9d1d9", linewidth=1.5)
    ax.annotate(name.split("(")[0].strip(),
                xy=(token_costs[name], resolve_rates[name]),
                xytext=(12, -5), textcoords="offset points",
                color=COLORS[name], fontsize=11, fontweight="bold")

# Connect Qwen points with dashed line
qwen_x = [token_costs[n] for n in ["E9 (100-step ACI)", "E11 (verify script)", "E12 (edit-nudge)"]]
qwen_y = [resolve_rates[n] for n in ["E9 (100-step ACI)", "E11 (verify script)", "E12 (edit-nudge)"]]
ax.plot(qwen_x, qwen_y, color="#8b949e", linestyle="--", linewidth=1.5, alpha=0.5)

# Opus: compute equivalent token cost for visual placement
# Opus total tokens
opus_tok = sum(t["total_input_tokens"] + t["total_output_tokens"] for t in opus_tasks) / 1e6
ax.scatter(opus_tok, resolve_rates["Opus 4.6"],
           color=COLORS["Opus 4.6"], s=200, zorder=5, marker="D",
           edgecolors="#c9d1d9", linewidth=1.5)
ax.annotate(f"Opus 4.6\n(${opus_cost:.0f})",
            xy=(opus_tok, resolve_rates["Opus 4.6"]),
            xytext=(12, 5), textcoords="offset points",
            color=COLORS["Opus 4.6"], fontsize=11, fontweight="bold")

ax.set_xlabel("Total Tokens (M)", fontsize=13)
ax.set_ylabel("Resolve Rate (%)", fontsize=13)
ax.set_title("Cost vs Performance Tradeoff (Hard Subset)", fontsize=15, fontweight="bold", pad=15)
ax.grid(alpha=0.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Annotation for Qwen = $0
ax.annotate("Qwen3.5-35B-A3B = $0 (self-hosted)",
            xy=(0.02, 0.02), xycoords="axes fraction",
            fontsize=10, color="#8b949e", style="italic")

fig.tight_layout()
fig.savefig(OUT / "hard_cost_vs_perf.png", bbox_inches="tight")
print("Saved hard_cost_vs_perf.png")

# ---------------------------------------------------------------------------
# Fig 5: Venn-style overlap heatmap
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))

strategies = ["Opus 4.6", "E12 (edit-nudge)", "E11 (verify script)", "E9 (100-step ACI)"]
res_sets = [set(opus_res), set(e12_res), set(e11_res), set(e9_res)]

n = len(strategies)
overlap = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        overlap[i, j] = len(res_sets[i] & res_sets[j])

im = ax.imshow(overlap, cmap="YlGn", aspect="auto", vmin=0, vmax=20)
ax.set_xticks(range(n))
ax.set_yticks(range(n))
ax.set_xticklabels([s.split("(")[0].strip() if "(" in s else s for s in strategies],
                    rotation=30, ha="right", fontsize=10)
ax.set_yticklabels([s.split("(")[0].strip() if "(" in s else s for s in strategies], fontsize=10)

for i in range(n):
    for j in range(n):
        v = int(overlap[i, j])
        ax.text(j, i, str(v), ha="center", va="center",
                fontsize=14, fontweight="bold",
                color="white" if v > 10 else "#c9d1d9")

ax.set_title("Pairwise Overlap — Resolved Tasks (Hard Subset)",
             fontsize=15, fontweight="bold", pad=15)
cbar = fig.colorbar(im, ax=ax, shrink=0.8)
cbar.ax.set_ylabel("Shared Resolves", fontsize=11, color="#c9d1d9")
cbar.ax.tick_params(colors="#8b949e")

fig.tight_layout()
fig.savefig(OUT / "hard_overlap_heatmap.png", bbox_inches="tight")
print("Saved hard_overlap_heatmap.png")

print("\nAll figures saved to figures/")
