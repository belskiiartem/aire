"""Static charts for the PDF report: two small multiples, one y-axis each."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.dates import DateFormatter  # noqa: E402
from datetime import datetime  # noqa: E402

FONTS = Path(__file__).resolve().parents[2] / "assets" / "fonts"
# Categorical slots in fixed order; colour follows the language, never its rank.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

for f in FONTS.glob("*.ttf"):
    font_manager.fontManager.addfont(str(f))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
                     "text.color": INK})


def colour_for(index: int) -> str:
    return SERIES[index % len(SERIES)]


def _panel(ax, series: dict[str, tuple[list[str], list[float]]], colours: dict[str, str], title: str, label_ends: bool):
    for lang, (months, values) in series.items():
        x = [datetime.strptime(m, "%Y-%m") for m in months]
        ax.plot(x, values, color=colours[lang], linewidth=2, label=lang, solid_capstyle="round")
        if label_ends and x:
            ax.annotate(lang, (x[-1], values[-1]), xytext=(4, 0), textcoords="offset points",
                        va="center", fontsize=8, color=INK_2)
    ax.set_title(title, loc="left", fontsize=9, color=INK)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_formatter(DateFormatter("%b %y"))
    ax.set_ylim(bottom=0)


def plot(raw: dict, indexed: dict, colours: dict[str, str], path: str, topic: str) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.1))
    few = len(raw) <= 4
    _panel(axes[0], raw, colours, "Monthly pageviews (human readers)", few)
    _panel(axes[1], indexed, colours, "Share of edition traffic, indexed (first 12 months = 100)", False)
    axes[1].axhline(100, color=INK_2, linewidth=0.8, linestyle=":")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper right", ncol=min(len(raw), 8),
               frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return path
