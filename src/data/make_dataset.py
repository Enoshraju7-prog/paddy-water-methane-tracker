"""One command fills `data/raw/`. Day 5 ship criterion.

    python -m src.data.make_dataset
    python -m src.data.make_dataset --skip-soil --skip-ndvi   # radar only, fast
    python -m src.data.make_dataset --sample                  # sample fields, no visit needed

Re-running is cheap: every fetcher checks the cache first, so a second run
should download nothing and finish in seconds. If it doesn't, the cache key is
wrong — fix that before day 6, because you will run this constantly.
"""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from src.config import FIELDS_DIR, RAW_DIR, ensure_dirs, settings
from src.data.fields import load_fields

app = typer.Typer(add_completion=False)


@app.command()
def main(
    sample: bool = typer.Option(False, help="Use the sample fields, not real boundaries."),
    skip_ndvi: bool = typer.Option(False, help="Skip Sentinel-2."),
    skip_weather: bool = typer.Option(False, help="Skip NASA POWER."),
    skip_soil: bool = typer.Option(False, help="Skip SoilGrids."),
) -> None:
    ensure_dirs()

    path = FIELDS_DIR / ("fields.sample.geojson" if sample else "fields.geojson")
    fields = load_fields(path)

    rprint(f"[bold]{len(fields)} fields[/bold], {fields['area_ha'].sum():.2f} ha total")
    rprint(f"pre-season {settings.preseason_start} → season end {settings.season_end}\n")

    results: dict[str, str] = {}

    # ── Sentinel-1: the one that matters ─────────────────────────────────────
    from src.data.sentinel1 import fetch_backscatter

    rprint("[cyan]Sentinel-1 RTC backscatter[/cyan] …")
    s1 = fetch_backscatter(fields)
    results["sentinel-1"] = (
        f"{len(s1)} obs, {s1['date'].nunique()} dates, "
        f"{s1['field_id'].nunique()} fields"
    )

    if not skip_ndvi:
        from src.data.sentinel2 import fetch_ndvi

        rprint("[cyan]Sentinel-2 NDVI[/cyan] …")
        s2 = fetch_ndvi(fields)
        results["sentinel-2"] = (
            f"{len(s2)} clear obs" if len(s2) else "no clear scenes (expected in monsoon)"
        )

    if not skip_weather:
        from src.data.weather import fetch_weather

        rprint("[cyan]NASA POWER[/cyan] …")
        weather = fetch_weather()
        results["nasa-power"] = f"{len(weather)} days"

    if not skip_soil:
        from src.data.soil import fetch_soil

        rprint("[cyan]SoilGrids[/cyan] …")
        soil = fetch_soil(fields)
        results["soilgrids"] = f"{len(soil)} fields"

    table = Table(title=f"data/raw/ populated — {RAW_DIR}")
    table.add_column("source")
    table.add_column("result")
    for source, summary in results.items():
        table.add_row(source, summary)
    rprint(table)

    rprint("\nnext: [bold]python -m src.features.build_features[/bold]")


if __name__ == "__main__":
    app()
