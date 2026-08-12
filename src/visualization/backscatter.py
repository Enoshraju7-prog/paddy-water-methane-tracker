"""Backscatter curves for the 12 Aug 2026 ground-truth walk, plotted two ways.

The question both figures answer: does the -16 dB flood rule agree with what was
actually standing in the fields on 12 Aug 2026? Every one of these 12 locations
held 5-7 cm of water when it was photographed, and the farmers say they never
drain. So the honest expectation is 12 out of 12 classified flooded.

Two figures because two different jobs:

  fig 1  small multiples - one panel per location. Twelve series on one axis
         would need twelve hues, and no palette survives that (see the series
         ladder in the dataviz notes). Faceting keeps one hue per measure.
  fig 2  diverging bar - distance from the threshold on the last available pass.
         "Above or below a baseline" is exactly what a diverging bar is for, and
         it puts the failure in a single glance.

    python -m src.visualization.backscatter
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import typer

from src.config import FIELDS_DIR, FIGURES_DIR, settings

# Palette slots, not raw taste. Categorical 1 and 2 for the two measures, the
# status "critical" step for the rule that is failing, and the muted/gridline
# steps so the furniture stays behind the data.
C_VV = "#2a78d6"
C_VH = "#eb6834"
C_BAD = "#d03b3b"
C_GOOD = "#0ca30c"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"

SERIES_CSV = FIELDS_DIR / "s1-clusters-2026-08-12.csv"

app = typer.Typer(add_completion=False)


def _style(ax) -> None:
    """Recessive furniture: hairline grid, no box, muted tick labels."""
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)


def timeline(df: pd.DataFrame, thr: float, out) -> None:
    """One panel per location. Shaded band = what the rule calls flooded."""
    ids = sorted(df.field_id.unique())
    ncol = 4
    nrow = -(-len(ids) // ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(13, 2.6 * nrow),
                             sharex=True, sharey=True)
    fig.patch.set_facecolor(SURFACE)

    lo = min(df.vh_db.min(), df.vv_db.min()) - 1.5
    hi = max(df.vh_db.max(), df.vv_db.max()) + 1.5

    for ax, fid in zip(axes.ravel(), ids):
        g = df[df.field_id == fid].sort_values("date").copy()
        # Real dates on a real time axis. Plotting the date STRINGS spaces every
        # pass equally, which hides the gaps where passes were dropped and makes
        # a 48-pass series unreadable when every tick gets a label.
        g["date"] = pd.to_datetime(g["date"])
        _style(ax)

        # The rule's own claim, drawn as territory rather than a bare line: any
        # point inside the band is called flooded. Emptiness here IS the finding.
        ax.axhspan(lo, thr, color=C_BAD, alpha=0.07, zorder=1)
        ax.axhline(thr, color=C_BAD, linewidth=1.4, linestyle=(0, (4, 3)), zorder=2)

        ax.plot(g.date, g.vv_db, color=C_VV, linewidth=2.0, marker="o",
                markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.2,
                zorder=4, label="VV")
        ax.plot(g.date, g.vh_db, color=C_VH, linewidth=2.0, marker="o",
                markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.2,
                zorder=3, label="VH")

        ax.set_title(fid, fontsize=10, color=INK, loc="left", fontweight="bold")
        ax.set_ylim(lo, hi)

    for ax in axes.ravel()[len(ids):]:
        ax.set_visible(False)

    span_days = (pd.to_datetime(df.date).max() - pd.to_datetime(df.date).min()).days
    every = 1 if span_days < 200 else (2 if span_days < 500 else 3)
    for ax in axes.ravel()[:len(ids)]:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=every))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%y"))
        ax.tick_params(axis="x", labelsize=8)
    for ax in axes[:, 0]:
        ax.set_ylabel("σ⁰  (dB)", fontsize=9, color=INK_2)

    axes.ravel()[0].legend(frameon=False, fontsize=9, loc="lower left",
                           labelcolor=INK_2, ncol=2)

    fig.text(0.008, 0.982, "Radar backscatter at 12 locations walked on 12 Aug 2026",
             fontsize=15, color=INK, fontweight="bold", ha="left", va="top")
    fig.text(0.008, 0.948,
             f"Shaded band = below {thr:g} dB, what the current rule calls flooded. "
             "All 12 locations held 5–7 cm of standing water when photographed.",
             fontsize=10, color=INK_2, ha="left", va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def distance_from_threshold(df: pd.DataFrame, thr: float, out) -> None:
    """How far each location sits from the rule, on the newest pass."""
    last = df.date.max()
    g = (df[df.date == last].set_index("field_id")
         .sort_values("vv_db")["vv_db"])
    gap = g - thr                      # >0 means the rule says DRY

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(SURFACE)
    _style(ax)

    colors = [C_BAD if v > 0 else C_GOOD for v in gap]
    ax.barh(g.index, gap, color=colors, height=0.62, zorder=3)
    ax.axvline(0, color=BASELINE, linewidth=1.4, zorder=4)

    # Direct labels, because color alone must never carry the verdict.
    for fid, v in gap.items():
        wrong = v > 0
        ax.text(v + (0.18 if wrong else -0.18), fid,
                f"{v:+.1f} dB   rule says {'DRY  ✗' if wrong else 'FLOODED  ✓'}",
                va="center", ha="left" if wrong else "right",
                fontsize=9, color=INK_2)

    n_wrong = int((gap > 0).sum())
    ax.set_xlim(gap.min() - 4.5, gap.max() + 4.5)
    ax.set_xlabel(f"distance from the {thr:g} dB threshold  (dB)",
                  fontsize=10, color=INK_2)
    fig.text(0.008, 0.982,
             f"{n_wrong} of {len(gap)} locations are called dry — "
             f"every one of them had water in it",
             fontsize=15, color=INK, fontweight="bold", ha="left", va="top")
    fig.text(0.008, 0.938,
             f"Sentinel-1 σ⁰ VV, descending relative orbit 19, pass of {last}. "
             "Ground truth from the walk of 12 Aug 2026.",
             fontsize=10, color=INK_2, ha="left", va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.905))
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


@app.command()
def main() -> None:
    df = pd.read_csv(SERIES_CSV, comment="#")
    thr = settings.s1_vv_flood_threshold_db
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    a = FIGURES_DIR / "backscatter-timeline-2026-08-12.png"
    b = FIGURES_DIR / "threshold-gap-2026-08-12.png"
    timeline(df, thr, a)
    distance_from_threshold(df, thr, b)
    typer.echo(f"wrote {a}\nwrote {b}")


if __name__ == "__main__":
    app()
