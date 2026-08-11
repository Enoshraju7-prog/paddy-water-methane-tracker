"""The first ground check, plotted: why a fixed -16 dB threshold failed.

On 11 Aug 2026 three fields in the Sarpavaram block were photographed holding
transplanted rice in standing water. The nearest radar pass (31 Jul) put all
three ABOVE the -16 dB flood threshold, i.e. it called them dry. This plot is
that failure, next to the thing that does separate them.

    python -m src.visualization.plot_validation
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.config import DOCS_IMG_DIR, VALIDATION_DIR, settings

CHECK_CSV = VALIDATION_DIR / "2026-08-11-first-ground-check.csv"

# Two pre-season passes, before any transplant flooding, define each field's own
# dry reference. Using the field against itself is the whole point - it removes
# the between-field offsets that a single global threshold cannot handle.
BASELINE_DATES = ["2026-05-01", "2026-05-13"]

LABELS = {
    "F001": "F001  observed flooded",
    "F002": "F002  observed flooded",
    "F003": "F003  observed flooded",
    "F004": "F004  radar-picked, not visited",
    "F900": "F900  negative control",
}
COLOURS = {"F001": "#1f77b4", "F002": "#2a9d8f", "F003": "#6a4c93",
           "F004": "#888888", "F900": "#d62828"}


def load() -> pd.DataFrame:
    df = pd.read_csv(CHECK_CSV, comment="#", parse_dates=["date"])
    return df.sort_values(["field_id", "date"])


def baseline_drop(df: pd.DataFrame, band: str = "vv_db") -> pd.DataFrame:
    """Each field's dB fall from its own pre-season mean, at the last pass."""
    base_mask = df["date"].isin(pd.to_datetime(BASELINE_DATES))
    base = df[base_mask].groupby("field_id")[band].mean()
    last = df.sort_values("date").groupby("field_id").tail(1).set_index("field_id")
    return pd.DataFrame({
        "baseline": base,
        "latest": last[band],
        "drop": base - last[band],
    })


def main() -> None:
    df = load()
    thr = settings.s1_vv_flood_threshold_db

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(14.5, 6),
                                 gridspec_kw={"width_ratios": [1.5, 1]})

    for fid, g in df.groupby("field_id"):
        ax.plot(g["date"], g["vv_db"], marker="o", color=COLOURS[fid], lw=2, ms=6,
                label=LABELS[fid],
                ls="--" if fid in ("F004", "F900") else "-")

    ax.axhline(thr, color="black", ls=":", lw=2)
    ax.text(df["date"].max(), thr + 0.3,
            f"{thr} dB threshold — 'flooded' below this line  ",
            fontsize=10, va="bottom", ha="right")
    ax.set_ylabel("Sentinel-1 VV  σ⁰  (dB)")
    ax.set_title("Three fields photographed flooded on 11 Aug.\n"
                 "On the nearest pass the threshold called all three DRY.",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()

    order = ["F001", "F002", "F003", "F004", "F900"]
    vv = baseline_drop(df, "vv_db").reindex(order)
    vh = baseline_drop(df, "vh_db").reindex(order)

    y = range(len(order))
    bx.barh([i - 0.2 for i in y], vv["drop"], height=0.38,
            color="#adb5bd", edgecolor="black", lw=0.6, label="VV")
    bx.barh([i + 0.2 for i in y], vh["drop"], height=0.38,
            color=[COLOURS[f] for f in order], edgecolor="black", lw=0.6,
            label="VH")
    bx.set_yticks(list(y))
    bx.set_yticklabels(order)
    bx.invert_yaxis()
    bx.set_xlabel("dB fallen from the field's OWN pre-season baseline")
    bx.set_title("VH separates; VV does not.\nBut the margin is ~1.7 dB on n=4 — not settled.",
                 fontsize=12, fontweight="bold")
    bx.legend(fontsize=9, loc="lower right")
    bx.grid(alpha=0.25, axis="x")

    fig.tight_layout()
    DOCS_IMG_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_IMG_DIR / "05-first-ground-check.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    print(f"wrote {out}\n")
    print("VV drop from baseline:")
    print(vv.round(1).to_string())
    print("\nVH drop from baseline:")
    print(vh.round(1).to_string())


if __name__ == "__main__":
    main()
