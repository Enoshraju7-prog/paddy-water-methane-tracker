"""The day-7 chart: VV backscatter over the season with flooded periods shaded.

    python -m src.visualization.plot_timeline --all
    python -m src.visualization.plot_timeline --field-id F001

This is the artefact that tells you whether the project works. Look at it before
you write another line of anything else. What you want to see:

  • a clear drop into flooded territory around transplanting
  • a floor around −17 to −20 dB while the field is ponded
  • a rise back up at harvest drainage
  • dips in the middle where drying events happened

What tells you something is wrong:

  • no separation at all → threshold is wrong, or the polygon is off the field
  • a steady climb from mid-season → canopy closure, not drainage (check NDVI)
  • sawtooth between passes → you are mixing orbit directions (pin one)
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import typer  # noqa: E402
from rich import print as rprint  # noqa: E402

from src.config import FIGURES_DIR, INTERIM_DIR, ensure_dirs, settings  # noqa: E402

app = typer.Typer(add_completion=False)


@app.command()
def main(
    field_id: str = typer.Option(None, help="Plot one field."),
    all_fields: bool = typer.Option(False, "--all", help="Plot every field."),
    show_rain: bool = typer.Option(True, help="Overlay NASA POWER rainfall."),
) -> None:
    ensure_dirs()

    path = INTERIM_DIR / "observations.parquet"
    if not path.exists():
        raise SystemExit("run `python -m src.features.build_features` first")

    observations = pd.read_parquet(path)

    rain = None
    if show_rain:
        try:
            from src.data.weather import fetch_weather

            rain = fetch_weather()
        except Exception as exc:  # noqa: BLE001 — a missing overlay must not block the chart
            rprint(f"[yellow]no rainfall overlay: {exc}[/yellow]")

    targets = (
        sorted(observations["field_id"].unique())
        if all_fields
        else [field_id or observations["field_id"].iloc[0]]
    )

    for target in targets:
        out = plot_field(observations, target, rain)
        rprint(f"wrote {out}")


def plot_field(observations: pd.DataFrame, field_id: str, rain: pd.DataFrame | None = None):
    obs = observations[observations["field_id"] == field_id].copy()
    obs["date"] = pd.to_datetime(obs["date"])
    obs = obs.sort_values("date")

    fig, ax = plt.subplots(figsize=(11, 4.5))

    # Shade each flooded interval — from a flooded observation to the next
    # observation of any kind. Nearest-neighbour in time, same rule the season
    # metrics use, so the picture and the numbers can't disagree.
    dates = obs["date"].tolist()
    for i, (_, row) in enumerate(obs.iterrows()):
        if not row["flooded"]:
            continue
        start = row["date"]
        end = dates[i + 1] if i + 1 < len(dates) else start + pd.Timedelta(days=12)
        ax.axvspan(start, end, color="#5b9bd5", alpha=0.22, lw=0)

    ax.plot(obs["date"], obs["vv_db"], "o-", color="#1f3864", ms=4, lw=1.4, label="σ⁰ VV")

    if "vh_db" in obs and obs["vh_db"].notna().any():
        ax.plot(obs["date"], obs["vh_db"], "o-", color="#a6a6a6", ms=3, lw=1,
                alpha=0.7, label="σ⁰ VH")

    threshold = obs["threshold_db"].iloc[0] if "threshold_db" in obs else \
        settings.s1_vv_flood_threshold_db
    ax.axhline(threshold, color="#c00000", ls="--", lw=1,
               label=f"flood threshold {threshold:g} dB")

    # Low-confidence observations (under closed canopy) get marked, not hidden.
    if "confidence" in obs:
        low = obs[obs["confidence"] == "low"]
        if len(low):
            ax.plot(low["date"], low["vv_db"], "x", color="#c00000", ms=9, mew=2,
                    label="low confidence (canopy)")

    ax.axvline(pd.Timestamp(settings.season_start), color="#404040", lw=0.8, alpha=0.6)
    ax.axvline(pd.Timestamp(settings.season_end), color="#404040", lw=0.8, alpha=0.6)

    if rain is not None and len(rain):
        rain_ax = ax.twinx()
        rain_ax.bar(pd.to_datetime(rain["date"]), rain["precip_mm"],
                    width=1.0, color="#9dc3e6", alpha=0.45, zorder=0)
        rain_ax.set_ylabel("rainfall (mm/day)", color="#5b9bd5", fontsize=9)
        rain_ax.set_ylim(0, max(120, float(rain["precip_mm"].max() or 0) * 1.1))
        rain_ax.tick_params(axis="y", labelcolor="#5b9bd5", labelsize=8)

    n_flooded = int(obs["flooded"].sum())
    ax.set_title(
        f"{field_id} — Sentinel-1 VV backscatter, shaded = flooded\n"
        f"{n_flooded}/{len(obs)} observations flooded  ·  "
        f"~12-day revisit: shorter drying events are invisible",
        fontsize=11, loc="left",
    )
    ax.set_ylabel("σ⁰ (dB)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.grid(alpha=0.25, lw=0.5)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    fig.autofmt_xdate()
    fig.tight_layout()

    out = FIGURES_DIR / f"timeline_{field_id}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


if __name__ == "__main__":
    app()
