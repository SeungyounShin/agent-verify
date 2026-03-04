"""Cumulative resolution vs steps — SWE-bench leaderboard style."""
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

# ---------------------------------------------------------------------------
# Style (matching leaderboard chart)
# ---------------------------------------------------------------------------
BG_COLOR = "#FAF6F1"
TEXT_DARK = "#2D2D2D"
TEXT_MID = "#666666"
GRID_COLOR = "#E0DCD6"
OPUS_COLOR = "#D4A574"

COLORS = {
    "Claude Opus 4.6":                          OPUS_COLOR,
    "Qwen3.5-35B-A3B (verify-on-edit)":         "#888888",
    "Qwen3.5-35B-A3B (verify-at-last)":         "#AAAAAA",
    "Qwen3.5-35B-A3B (agent-harness)":           "#CCCCCC",
}
LINE_STYLES = {
    "Claude Opus 4.6":                          "-",
    "Qwen3.5-35B-A3B (verify-on-edit)":         "-",
    "Qwen3.5-35B-A3B (verify-at-last)":         "--",
    "Qwen3.5-35B-A3B (agent-harness)":           ":",
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

hard_ids = {t["task_id"] for t in opus_tasks}
e9_all = load_summary("results/exp9_100step_compaction/exp9_100step_compaction_summary.json")
e9_tasks = [t for t in e9_all if t["task_id"] in hard_ids]

opus_res = set(json.load(open("hard_opus.hard_opus.json"))["resolved_ids"])
e12_res = set(json.load(open("exp12_hard45_final.exp12_hard45_final.json"))["resolved_ids"])
e11_res = set(json.load(open("exp11_hard45_v2.exp11_hard45_v2.json"))["resolved_ids"])
e9_res_full = set(json.load(open("exp-log/docker_reports/exp9_final.exp9_final.json"))["resolved_ids"])
e9_res = e9_res_full & hard_ids

# ---------------------------------------------------------------------------
# Cumulative function
# ---------------------------------------------------------------------------
def cumulative_resolved(tasks, resolved_set, max_step=200):
    resolved_steps = sorted(t["total_steps"] for t in tasks if t["task_id"] in resolved_set)
    steps_range = np.arange(1, max_step + 1)
    cum = [sum(1 for s in resolved_steps if s <= x) for x in steps_range]
    return steps_range, cum

configs = [
    ("Claude Opus 4.6",                          opus_tasks, opus_res, 100),
    ("Qwen3.5-35B-A3B (verify-on-edit)",         e12_tasks,  e12_res,  200),
    ("Qwen3.5-35B-A3B (verify-at-last)",         e11_tasks,  e11_res,  200),
    ("Qwen3.5-35B-A3B (agent-harness)",           e9_tasks,   e9_res,   100),
]

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 7))
fig.patch.set_facecolor(BG_COLOR)
ax.set_facecolor(BG_COLOR)

for name, tasks, res, ms in configs:
    x, y = cumulative_resolved(tasks, res, ms)
    y_frac = [v / 45 * 100 for v in y]
    ax.plot(x, y_frac, label=name, color=COLORS[name],
            linestyle=LINE_STYLES[name], linewidth=3, alpha=0.9)
    # End marker
    ax.scatter([x[-1]], [y_frac[-1]], color=COLORS[name], s=80, zorder=5,
               edgecolors="white", linewidth=1.5)
    # End label
    ax.annotate(f"{y[-1]}/45 ({y_frac[-1]:.1f}%)",
                xy=(x[-1], y_frac[-1]),
                xytext=(10, 0), textcoords="offset points",
                color=COLORS[name], fontsize=11, fontweight="bold", va="center")

ax.set_xlabel("Steps", fontsize=14, color=TEXT_DARK)
ax.set_ylabel("Cumulative Resolve Rate (%)", fontsize=14, color=TEXT_DARK)
ax.set_title("SWE-bench Verified Hard — Cumulative Resolution vs Steps",
             fontsize=20, fontweight="bold", color=TEXT_DARK,
             fontfamily="sans-serif", pad=20, loc="left")

ax.set_xlim(0, 215)
ax.set_ylim(0, 50)
ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
ax.xaxis.set_major_locator(mticker.MultipleLocator(25))
ax.grid(alpha=0.4, color=GRID_COLOR)

for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_color(TEXT_DARK)
ax.spines["left"].set_color(TEXT_DARK)
ax.tick_params(colors=TEXT_MID)

leg = ax.legend(loc="upper left", fontsize=11, frameon=True,
                facecolor=BG_COLOR, edgecolor="#DDDDDD", framealpha=1)
for text in leg.get_texts():
    text.set_color(TEXT_DARK)

fig.text(0.98, 0.02, "agent-verify", fontsize=11, color=TEXT_MID,
         ha="right", va="bottom", fontfamily="sans-serif")

fig.tight_layout()
fig.savefig(OUT / "hard_cumulative_steps.png", bbox_inches="tight", dpi=150,
            facecolor=BG_COLOR)
print("Saved hard_cumulative_steps.png")
