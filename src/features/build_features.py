"""Day 6–7 entry point: raw backscatter → classified observations → season metrics.

    python -m src.features.build_features
    python -m src.features.build_features --threshold -15.5   # after day 8 tuning

Writes:
    data/interim/observations.parquet    one row per field per date, flooded/dry
    data/interim/season_metrics.parquet  one row per field
"""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from src.config import INTERIM_DIR, ensure_dirs, settings
from src.data.fields import load_fields
from src.data.sentinel1 import fetch_backscatter
from src.features.flooding import classify
from src.features.season import compute_all

app = typer.Typer(add_completion=False)


@app.command()
def main(
    sample: bool = typer.Option(False, help="Use the sample fields."),
    threshold: float = typer.Option(None, help="Override the VV flood threshold, dB."),
    use_ndvi: bool = typer.Option(True, help="Downgrade confidence after canopy closure."),
) -> None:
    ensure_dirs()

    from src.config import FIELDS_DIR

    fields = load_fields(
        FIELDS_DIR / ("fields.sample.geojson" if sample else "fields.geojson")
    )
    backscatter = fetch_backscatter(fields)

    ndvi = None
    if use_ndvi:
        from src.data.sentinel2 import fetch_ndvi

        ndvi = fetch_ndvi(fields)
        if ndvi.empty:
            rprint("[yellow]no clear Sentinel-2 scenes — no canopy flagging[/yellow]")
            ndvi = None

    observations = classify(backscatter, ndvi=ndvi, threshold_db=threshold)
    metrics = compute_all(observations)

    observations.to_parquet(INTERIM_DIR / "observations.parquet", index=False)
    metrics.to_parquet(INTERIM_DIR / "season_metrics.parquet", index=False)

    used = threshold if threshold is not None else settings.s1_vv_flood_threshold_db
    table = Table(title=f"season metrics — threshold {used} dB")
    for column in ("field_id", "n_observations", "days_flooded", "n_drying_events",
                   "preseason_flooded", "mean_revisit_days"):
        table.add_column(column)
    for _, row in metrics.iterrows():
        table.add_row(
            row["field_id"],
            str(row["n_observations"]),
            str(row["days_flooded"]),
            str(row["n_drying_events"]),
            "yes" if row["preseason_flooded"] else "no",
            f"{row['mean_revisit_days']:.1f}",
        )
    rprint(table)

    rprint(
        "\n[dim]drying-event counts are a LOWER BOUND — a ~12-day revisit cannot "
        "see shorter events[/dim]"
    )
    rprint("next: [bold]python -m src.visualization.plot_timeline --all[/bold]")


if __name__ == "__main__":
    app()
