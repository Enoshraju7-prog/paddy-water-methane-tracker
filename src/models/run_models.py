"""Day 9 entry point: season metrics → methane, AWD scenario, water and cost.

    python -m src.models.run_models

Reads   data/interim/season_metrics.parquet
Writes  data/processed/season_results.parquet   ← this is what Postgres loads
"""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import typer
from rich import print as rprint
from rich.table import Table

from src.config import FIELDS_DIR, INTERIM_DIR, PROCESSED_DIR, ensure_dirs, settings
from src.data.fields import load_fields
from src.models import methane, water

app = typer.Typer(add_completion=False)


@app.command()
def main(sample: bool = typer.Option(False, help="Use the sample fields.")) -> None:
    ensure_dirs()

    metrics_path = INTERIM_DIR / "season_metrics.parquet"
    if not metrics_path.exists():
        raise SystemExit("run `python -m src.features.build_features` first")

    metrics = pd.read_parquet(metrics_path)
    fields = load_fields(
        FIELDS_DIR / ("fields.sample.geojson" if sample else "fields.geojson")
    ).set_index("field_id")

    rows = []
    for _, row in metrics.iterrows():
        field_id = row["field_id"]
        if field_id not in fields.index:
            rprint(f"[yellow]{field_id}: no boundary, skipped[/yellow]")
            continue
        field = fields.loc[field_id]

        # Cultivation days from the farmer's own transplant/harvest dates when
        # we have them — those beat the season-wide default every time.
        cultivation_days = _cultivation_days(field)

        amendments = methane.parse_amendments(
            field.get("straw_management"), field.get("days_before_flooding")
        )

        ch4 = methane.estimate(
            field_id=field_id,
            area_ha=float(field["area_ha"]),
            cultivation_days=cultivation_days,
            n_drying_events=int(row["n_drying_events"]),
            preseason_flooded_days=int(row["preseason_flooded_days"]),
            amendments=amendments,
        )
        h2o = water.estimate(field_id=field_id, area_ha=float(field["area_ha"]))

        rows.append(
            {
                **asdict(ch4),
                **{k: v for k, v in asdict(h2o).items() if k not in {"field_id", "area_ha"}},
                "days_flooded": int(row["days_flooded"]),
                "n_drying_events": int(row["n_drying_events"]),
                "n_observations": int(row["n_observations"]),
                "mean_revisit_days": float(row["mean_revisit_days"]),
                "low_confidence_fraction": float(row["low_confidence_fraction"]),
            }
        )

    results = pd.DataFrame(rows)
    results["assumptions"] = results["assumptions"].astype(str)
    out = PROCESSED_DIR / "season_results.parquet"
    results.to_parquet(out, index=False)

    table = Table(title=f"season results — GWP100 = {settings.gwp_ch4}")
    for column in ("field_id", "ha", "regime", "tCO2e", "range", "AWD avoided", "₹ saved"):
        table.add_column(column)
    for _, r in results.iterrows():
        table.add_row(
            r["field_id"],
            f"{r['area_ha']:.2f}",
            r["water_regime"].replace("_", " "),
            f"{r['co2e_tonnes']:.2f}",
            f"{r['co2e_tonnes_low']:.2f}–{r['co2e_tonnes_high']:.2f}",
            f"{r['co2e_avoided_tonnes']:.2f} ({r['pct_reduction']:.0f}%)",
            f"{r['cost_saved_inr_low']:.0f}–{r['cost_saved_inr_high']:.0f}",
        )
    rprint(table)
    rprint(f"\nwrote [bold]{out}[/bold]")
    rprint(
        "[dim]not decision-grade: EF_c carries ±40%, drying events are undercounted "
        "by the revisit gap, and straw data is from recall[/dim]"
    )


def _cultivation_days(field) -> int:
    transplant, harvest = field.get("transplant_date"), field.get("harvest_date")
    if transplant and harvest:
        try:
            days = (pd.Timestamp(harvest) - pd.Timestamp(transplant)).days
            if 60 <= days <= 200:
                return days
        except (TypeError, ValueError):
            pass
    return settings.default_cultivation_days


if __name__ == "__main__":
    app()
