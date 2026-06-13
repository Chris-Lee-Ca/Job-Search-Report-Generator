"""Generate the application ratio trend chart as a PNG."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

CHART_PATH = Path("output/application_trend.png")


def generate_trend_chart(stats: dict[str, dict], out_path: Path = CHART_PATH) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import numpy as np

    # Sort entries; only include days that have both scored and applied recorded
    rows = sorted(
        [(d, v) for d, v in stats.items() if "scored" in v and "applied" in v],
        key=lambda x: x[0],
    )
    if len(rows) < 2:
        return

    dates = [datetime.strptime(d, "%Y-%m-%d") for d, _ in rows]
    scored = [v["scored"] for _, v in rows]
    applied = [v["applied"] for _, v in rows]
    ratios = [a / s * 100 if s else 0 for a, s in zip(applied, scored)]

    # 7-day rolling average of ratio (use available window when fewer than 7 days)
    rolling = []
    for i in range(len(ratios)):
        window = ratios[max(0, i - 6) : i + 1]
        rolling.append(sum(window) / len(window))

    fig, ax1 = plt.subplots(figsize=(13, 5))
    fig.patch.set_facecolor("#0f0f0f")
    ax1.set_facecolor("#0f0f0f")

    x = np.arange(len(dates))
    bar_w = 0.38

    # Bars: scored (dim) and applied (bright)
    ax1.bar(x - bar_w / 2, scored, bar_w, label="Scored", color="#2a4a6b", zorder=2)
    ax1.bar(x + bar_w / 2, applied, bar_w, label="Applied", color="#2db5a3", zorder=2)

    ax1.set_ylabel("Jobs / day", color="#aaaaaa", fontsize=10)
    ax1.tick_params(axis="y", colors="#aaaaaa")
    ax1.tick_params(axis="x", colors="#aaaaaa", rotation=45)
    ax1.set_xticks(x)
    ax1.set_xticklabels(
        [d.strftime("%b %d") for d in dates], fontsize=8, ha="right"
    )
    ax1.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    for spine in ax1.spines.values():
        spine.set_edgecolor("#333333")
    ax1.grid(axis="y", color="#222222", linewidth=0.6, zorder=1)

    # Second Y axis: ratio %
    ax2 = ax1.twinx()
    ax2.set_facecolor("#0f0f0f")
    ax2.plot(x, ratios, "o-", color="#f5a623", linewidth=1.5, markersize=4,
             label="Daily ratio", zorder=4)
    ax2.plot(x, rolling, "--", color="#e87070", linewidth=1.5,
             label="7-day avg", zorder=4)
    ax2.axhline(20, color="#666666", linewidth=0.8, linestyle=":", zorder=3)
    ax2.text(len(dates) - 0.5, 21, "target 20%", color="#666666",
             fontsize=8, ha="right", va="bottom")

    ax2.set_ylabel("Applied / Scored (%)", color="#aaaaaa", fontsize=10)
    ax2.tick_params(axis="y", colors="#aaaaaa")
    ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax2.set_ylim(0, max(max(ratios) * 1.3, 25))
    for spine in ax2.spines.values():
        spine.set_edgecolor("#333333")

    # Latest ratio callout
    latest_ratio = ratios[-1]
    avg_ratio = sum(ratios) / len(ratios)
    fig.suptitle(
        f"Application Ratio Trend  |  Latest: {latest_ratio:.1f}%  |  Avg: {avg_ratio:.1f}%",
        color="#dddddd", fontsize=12, fontweight="bold", y=1.01,
    )

    # Combined legend
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(
        handles1 + handles2, labels1 + labels2,
        loc="upper left", fontsize=8,
        facecolor="#1a1a1a", edgecolor="#333333", labelcolor="#cccccc",
    )

    fig.tight_layout()
    out_path.parent.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
