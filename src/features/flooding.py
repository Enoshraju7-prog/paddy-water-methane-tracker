"""Flood classification from Sentinel-1, and an honest score for it.

THE RULE THIS REPLACES. v1 asked "is sigma-nought VV below -16 dB?". Measured on
12 Aug 2026 against 12 locations photographed 15 minutes after the pass, every
one of them holding 5-7 cm of standing water, that rule scored 0 out of 12.

WHY IT FAILED. Open water is dark because it mirrors the pulse away. But a rice
field is not open water — it is stems standing IN water, and a stem plus a water
surface is a corner reflector. The pulse bounces off the water, off the stem, and
straight back. That is double bounce, and it makes a flooded, growing paddy
BRIGHT. Only the bare puddled field in the fortnight after transplanting is dark.
So an absolute darkness threshold detects the puddling window, not the season.

THE RULE HERE. Compare each field to ITSELF:

    drop = baseline_VH - current_VH          (positive = it got darker)
    flooded if drop >= vh_drop_threshold_db

`baseline` is the field's own median VH over a dry reference window before the
season. Three consequences worth understanding:

  1. It removes the between-field differences that broke the absolute rule. One
     field sitting 3 dB brighter than its neighbour because of soil or row
     direction no longer matters — only its own change does.
  2. A difference cancels any constant calibration offset, so a sigma0 baseline
     and a gamma0 observation can be compared. The absolute rule could not.
  3. VH rather than VV because VH falls further when a paddy floods. On 12 Aug
     VV separated nothing; VH separated most of it.

WHAT IT STILL CANNOT DO. It says flooded or not flooded. It does NOT say AWD:
telling deliberate wetting-and-drying apart from continuous flooding at a 12-day
revisit tops out around F1 0.74 in the published literature. Do not claim it.

    python -m src.features.flooding              # classify + score
    python -m src.features.flooding --sweep      # try every threshold
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import typer
from rich import print as rprint
from rich.table import Table

from src.config import FIELDS_DIR, settings

app = typer.Typer(add_completion=False)

ARCHIVE_CSV = FIELDS_DIR / "s1-clusters-preseason.csv"   # sigma0, Planetary Computer
SAME_DAY_CSV = FIELDS_DIR / "s1-cdse-same-day.csv"       # gamma0, CDSE
LABELS_CSV = FIELDS_DIR / "ground_truth-clusters.csv"
OUT_CSV = FIELDS_DIR / "flood-flags.csv"


def load_series() -> pd.DataFrame:
    """Archive plus same-day, stacked, with the source kept on every row."""
    frames = []
    if ARCHIVE_CSV.exists():
        a = pd.read_csv(ARCHIVE_CSV, comment="#")
        a["source"] = a.get("source", "pc-sigma0-rtc")
        frames.append(a)
    if SAME_DAY_CSV.exists():
        frames.append(pd.read_csv(SAME_DAY_CSV, comment="#"))

    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    # Same field, same day, two sources: keep the archive. RTC is the record of
    # truth; a CDSE reading is provisional until RTC catches up.
    return (df.sort_values(["field_id", "date", "source"])
              .drop_duplicates(["field_id", "date"], keep="first")
              .reset_index(drop=True))


def baselines(df: pd.DataFrame, ref_start, ref_end) -> pd.DataFrame:
    """Each field's own dry-season VH level.

    MEDIAN, not mean, and that is not a style choice. Taking a *mean* of decibel
    values is the classic sigma-nought error — dB is logarithmic, so the mean has
    to happen in linear power. A median is safe either way: it is order-based, and
    dB is a monotonic function of power, so the median of the dB values IS the dB
    of the median power. Same number, no conversion, and robust to one odd pass.
    """
    ref = df[(df.date >= pd.Timestamp(ref_start)) & (df.date < pd.Timestamp(ref_end))]
    out = (ref.groupby("field_id")
              .agg(baseline_vh=("vh_db", "median"),
                   baseline_vv=("vv_db", "median"),
                   n_ref=("vh_db", "size"))
              .reset_index())
    return out[out.n_ref >= settings.min_baseline_obs]


def classify(df: pd.DataFrame, base: pd.DataFrame, thr: float) -> pd.DataFrame:
    m = df.merge(base, on="field_id", how="inner")
    m["vh_drop_db"] = m.baseline_vh - m.vh_db
    m["vv_drop_db"] = m.baseline_vv - m.vv_db
    m["flooded"] = m.vh_drop_db >= thr
    return m


def score(flags: pd.DataFrame, labels: pd.DataFrame) -> dict:
    """Compare to what was actually seen on the ground. No partial credit."""
    j = labels.merge(flags, on=["field_id", "date"], how="inner")
    if j.empty:
        return {"n": 0}
    tp = int((j.observed_flooded & j.flooded).sum())
    fn = int((j.observed_flooded & ~j.flooded).sum())
    fp = int((~j.observed_flooded & j.flooded).sum())
    tn = int((~j.observed_flooded & ~j.flooded).sum())
    n = len(j)
    return {"n": n, "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "correct": tp + tn, "accuracy": (tp + tn) / n}


def _prepare(ref_start=None, ref_end=None):
    df = load_series()
    end = pd.Timestamp(ref_end) if ref_end else pd.Timestamp(settings.season_2026_start)
    start = pd.Timestamp(ref_start) if ref_start else end - timedelta(
        days=settings.baseline_days)
    base = baselines(df, start, end)
    labels = pd.read_csv(LABELS_CSV)
    labels["date"] = pd.to_datetime(labels["date"])
    return df, base, labels, start, end


@app.command()
def main(
    sweep: bool = typer.Option(False, "--sweep", help="score every threshold"),
    ref_start: str = typer.Option(None, help="dry reference window start"),
    ref_end: str = typer.Option(None, help="dry reference window end"),
) -> None:
    df, base, labels, start, end = _prepare(ref_start, ref_end)
    rprint(f"[dim]reference window {start:%d %b %Y} → {end:%d %b %Y}  ·  "
           f"{len(base)} fields with a usable baseline  ·  "
           f"{df.date.nunique()} passes[/dim]\n")

    if sweep:
        t = Table(title="VH-drop threshold sweep — scored on the 12 Aug walk")
        for c, j in (("drop ≥", "right"), ("correct", "right"),
                     ("accuracy", "right"), ("missed", "left")):
            t.add_column(c, justify=j)
        for thr in [x / 2 for x in range(17)]:
            s = score(classify(df, base, thr), labels)
            missed = ", ".join(
                sorted(classify(df, base, thr)
                       .merge(labels, on=["field_id", "date"])
                       .query("observed_flooded and not flooded").field_id))
            t.add_row(f"{thr:.1f} dB", f"{s['correct']}/{s['n']}",
                      f"{s['accuracy']:.0%}", missed[:46] or "—")
        rprint(t)
        # The absolute rule, for comparison. A new rule that is not compared to
        # the one it replaces is not a result.
        same = df[df.date == pd.Timestamp("2026-08-12")]
        old = int((same.vv_db <= settings.s1_vv_flood_threshold_db).sum())
        rprint(f"\n[dim]for comparison — old rule (VV ≤ "
               f"{settings.s1_vv_flood_threshold_db:g} dB): "
               f"{old}/{len(same)}[/dim]")
        return

    thr = settings.vh_drop_threshold_db
    flags = classify(df, base, thr)
    flags.to_csv(OUT_CSV, index=False)
    s = score(flags, labels)

    same = flags[flags.date == pd.Timestamp("2026-08-12")].sort_values("vh_drop_db")
    t = Table(title=f"12 Aug 2026 — VH-drop rule at {thr:g} dB")
    for c in ("field", "baseline VH", "VH today", "drop", "verdict"):
        t.add_column(c, justify="right" if c != "verdict" else "left")
    for r in same.itertuples():
        t.add_row(r.field_id, f"{r.baseline_vh:.1f}", f"{r.vh_db:.1f}",
                  f"{r.vh_drop_db:+.1f} dB",
                  "[green]flooded ✓[/green]" if r.flooded else "[red]dry ✗[/red]")
    rprint(t)
    rprint(f"\n[bold]{s['correct']}/{s['n']} correct ({s['accuracy']:.0%})[/bold]"
           f"   ·   old VV rule: 0/12"
           f"\n[dim]wrote {OUT_CSV}[/dim]")


if __name__ == "__main__":
    app()
