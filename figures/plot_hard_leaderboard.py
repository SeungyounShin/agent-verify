"""SWE-bench Verified Hard leaderboard chart — matches official SWE-bench style."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ---------------------------------------------------------------------------
# Data (sorted by resolve rate descending)
# ---------------------------------------------------------------------------
entries = [
    {"name": "Opus 4.6",                "pct": 40.0, "cost": "$62",    "type": "opus"},
    {"name": "E12\n(edit-nudge)",        "pct": 37.8, "cost": "$0",     "type": "qwen"},
    {"name": "E11\n(verify script)",     "pct": 33.3, "cost": "$0",     "type": "qwen"},
    {"name": "E9\n(100-step ACI)",       "pct": 22.2, "cost": "$0",     "type": "qwen"},
    {"name": "E8\n(200-step ACI)",       "pct": 17.8, "cost": "$0",     "type": "qwen"},
]

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
BG_COLOR = "#FAF6F1"           # warm cream background (matches reference)
OPUS_COLOR = "#D4A574"         # Claude brown/tan
QWEN_GRAY = "#C8C8C8"         # neutral gray for Qwen
TEXT_DARK = "#2D2D2D"
TEXT_MID = "#666666"
BAR_EDGE = "none"

def get_color(entry):
    return OPUS_COLOR if entry["type"] == "opus" else QWEN_GRAY

# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(14, 8))
fig.patch.set_facecolor(BG_COLOR)
ax.set_facecolor(BG_COLOR)

n = len(entries)
x = np.arange(n)
bar_width = 0.65

# Draw bars
colors = [get_color(e) for e in entries]
bars = ax.bar(x, [e["pct"] for e in entries], width=bar_width,
              color=colors, edgecolor=BAR_EDGE, linewidth=0, zorder=2)

# Percentage + cost labels above bars
for i, (bar, entry) in enumerate(zip(bars, entries)):
    y_top = bar.get_height()
    # Percentage (big, bold)
    ax.text(bar.get_x() + bar.get_width() / 2, y_top + 1.2,
            f"{entry['pct']:.1f}%",
            ha="center", va="bottom", fontsize=18, fontweight="bold",
            color=TEXT_DARK, fontfamily="sans-serif")
    # Cost (smaller, below percentage)
    ax.text(bar.get_x() + bar.get_width() / 2, y_top + 0.2,
            entry["cost"],
            ha="center", va="top", fontsize=12,
            color=TEXT_MID, fontfamily="sans-serif")

# X-axis labels (rotated like reference)
ax.set_xticks(x)
ax.set_xticklabels([e["name"] for e in entries],
                    fontsize=13, color=TEXT_DARK, fontweight="medium",
                    rotation=30, ha="right", fontfamily="sans-serif")

# Remove all spines except bottom
for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_color(TEXT_DARK)
ax.spines["bottom"].set_linewidth(2)

# Remove y-axis
ax.yaxis.set_visible(False)
ax.tick_params(axis="x", length=0, pad=8)

# Set limits
ax.set_ylim(0, max(e["pct"] for e in entries) + 10)
ax.set_xlim(-0.5, n - 0.5)

# Title
ax.set_title("SWE-bench Verified Hard (45 tasks)",
             fontsize=24, fontweight="bold", color=TEXT_DARK,
             fontfamily="sans-serif", pad=25, loc="left")

# Subtitle
ax.text(0.0, 1.02, "Qwen3.5-35B-A3B (3B active, self-hosted) vs Claude Opus 4.6",
        transform=ax.transAxes, fontsize=13, color=TEXT_MID,
        fontfamily="sans-serif", va="bottom")

# Legend
legend_elements = [
    mpatches.Patch(facecolor=OPUS_COLOR, label="Claude Opus 4.6"),
    mpatches.Patch(facecolor=QWEN_GRAY, label="Qwen3.5-35B-A3B"),
]
leg = ax.legend(handles=legend_elements, loc="upper right",
                fontsize=12, frameon=True, facecolor=BG_COLOR,
                edgecolor="#DDDDDD", framealpha=1)
for text in leg.get_texts():
    text.set_color(TEXT_DARK)

# Footer
fig.text(0.98, 0.02, "agent-verify", fontsize=11, color=TEXT_MID,
         ha="right", va="bottom", fontfamily="sans-serif")

fig.tight_layout(rect=[0, 0.03, 1, 0.95])
fig.savefig("figures/hard_leaderboard.png", bbox_inches="tight", dpi=150,
            facecolor=BG_COLOR)
print("Saved figures/hard_leaderboard.png")
