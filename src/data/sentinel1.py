"""Sentinel-1 radar backscatter per field, per pass. The core signal.

Why radar and not an ordinary camera: this is a monsoon season. An optical
satellite spends most of kharif looking at cloud tops. Radar is its own light
source at a wavelength that passes straight through cloud, and it works at night.

Why it detects water: still water is a *specular* reflector. It bounces the radar
pulse away from the satellite like a mirror, so almost nothing comes back and the
pixel reads dark. Rough surfaces — soil clods, a rice canopy — scatter in all
directions, including back up. Typical σ⁰ VV:

    ponded paddy  -22 … -17 dB     bare/drained  ~ -10 dB
    peak rice canopy  -16 … -14 dB

That contrast is the entire basis of this project — and note how narrow the third
figure makes it. Rice closes canopy over standing water, so peak-season VV rises
only into the -16 … -14 dB band, not the ~ -7 dB a generic land-cover table gives
for dense vegetation. Mid-season can therefore sit within ~1 dB of the -16 dB
flood threshold. See `s1_vv_flood_threshold_db` in config.

    python -m src.data.sentinel1 --field F001      # one field, printed
    python -m src.data.sentinel1                   # all fields → parquet
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import typer

from src.config import INTERIM_DIR, CRS_UTM_44N, settings
from src.data.cache import disk_cache

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# RTC — Radiometrically Terrain Corrected. Worth the words: raw radar brightness
# depends on the local slope, so the same crop reads differently on a hillside
# than on the flat. RTC removes that. The delta is flat so it matters less here
# than in hill country, but it also arrives calibrated to σ⁰, which is what the
# -16 dB threshold is defined against. Using GRD instead would need calibration
# by hand.
COLLECTION = "sentinel-1-rtc"

# 10 m native. A 0.5 ha field is ~45 x 45 m ≈ 20 pixels — enough to average,
# small enough that polygon sloppiness shows up in the numbers.
RESOLUTION_M = 10

# Below this many valid pixels a field-date mean is too noisy to trust. Two
# pixels can be two lucky puddles.
MIN_PIXELS = 5


@dataclass
class FieldSeries:
    field_id: str
    dates: list[date]
    vv_db: list[float]
    vh_db: list[float]
    n_pixels: list[int]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "field_id": self.field_id,
            "date": self.dates,
            "vv_db": self.vv_db,
            "vh_db": self.vh_db,
            "n_pixels": self.n_pixels,
        })


def to_db(linear: np.ndarray | float) -> np.ndarray | float:
    """Linear power → decibels. Zero and negative map to NaN, not -inf."""
    linear = np.asarray(linear, dtype="float64")
    return np.where(linear > 0, 10 * np.log10(np.where(linear > 0, linear, 1)), np.nan)


def mean_db(linear_values: np.ndarray) -> float:
    """Average in LINEAR power, then convert. Never the other way round.

    ── Trap 2 of 3, and the most seductive one, because averaging dB directly
    produces numbers that look completely reasonable. ──

    dB is logarithmic. Averaging logs computes a geometric mean of the
    underlying powers, which is always ≤ the true arithmetic mean, and the gap
    widens with variance. A part-flooded field has high variance, so the error
    is largest exactly where the field is transitioning — biasing those fields
    toward "flooded" and inventing a smooth curve where the truth is patchy.

    Worked example: pixels at -20 dB and -5 dB.
        wrong:  (-20 + -5) / 2                        = -12.5 dB
        right:  10*log10((0.01 + 0.316) / 2)          =  -7.9 dB
    A 4.6 dB gap straddling the -16 dB threshold.
    """
    valid = linear_values[np.isfinite(linear_values) & (linear_values > 0)]
    if valid.size == 0:
        return float("nan")
    return float(10 * np.log10(valid.mean()))


def _search_items(bbox: tuple, start: date, end: date) -> list:
    """STAC items for the bbox and window, one orbit direction only.

    ── Trap 1 of 3: mixed orbit directions. ──
    Ascending (evening) and descending (morning) passes view the same field from
    opposite sides at different incidence angles, so they return systematically
    different backscatter for an unchanged field. Interleave them and the time
    series develops a sawtooth that a threshold reads as the field flooding and
    drying every few days. Pin one direction and accept the coarser revisit.
    Here it costs nothing: this bbox has descending coverage only.
    """
    import planetary_computer
    import pystac_client

    catalog = pystac_client.Client.open(
        STAC_URL, modifier=planetary_computer.sign_inplace
    )
    items = list(
        catalog.search(
            collections=[COLLECTION], bbox=list(bbox), datetime=f"{start}/{end}"
        ).items()
    )

    wanted = settings.s1_orbit_direction
    if wanted != "any":
        items = [i for i in items if i.properties.get("sat:orbit_state") == wanted]

    # ── Trap 3 of 3: tile order when mosaicking. ──
    # One pass arrives as two or more overlapping slices. Loaded in the order
    # the catalogue happens to return them, the later slice's nodata overwrites
    # the earlier slice's real data — measured at 93% of this study area lost,
    # with no error raised. Sorting by acquisition time fixes it; the
    # valid-pixel assertion downstream catches it if it ever regresses.
    items.sort(key=lambda i: i.properties["datetime"])
    return items


@disk_cache("s1_scene")
def load_scenes(
    bbox: tuple[float, float, float, float], start: date, end: date
) -> "xr.Dataset":  # type: ignore # noqa: F821
    """Load every pass over a bbox as a single cube (time, y, x).

    **Pass a field-sized bbox, not the study area.** The whole 50 x 50 km box at
    10 m over a season is ~5000 x 5000 x 30 passes x 2 bands ≈ 6 GB — it will
    swap your laptop to death. A single field's bbox is a few hundred pixels
    across and downloads in seconds. `series_for_fields` handles this for you.
    """
    import odc.stac

    items = _search_items(bbox, start, end)
    if not items:
        raise RuntimeError(
            f"No {COLLECTION} scenes for bbox {bbox} in {start}..{end} "
            f"(orbit={settings.s1_orbit_direction}). Try --orbit any."
        )

    ds = odc.stac.load(
        items,
        bands=["vv", "vh"],
        bbox=list(bbox),
        crs=CRS_UTM_44N,
        resolution=RESOLUTION_M,
        groupby="solar_day",   # fuse the slices of one pass into one time step
        chunks={},
    ).compute()

    # The assertion that makes trap 3 loud instead of silent.
    valid_fraction = float((ds["vv"] > 0).mean())
    if valid_fraction < 0.5:
        raise RuntimeError(
            f"Only {valid_fraction:.1%} of the loaded cube has valid data. "
            f"Expected >50%. This is usually the mosaic-ordering bug — check "
            f"that items are sorted by acquisition time and groupby='solar_day'."
        )

    return ds


def series_for_field(ds, geometry, field_id: str) -> FieldSeries:
    """Mask the cube to one polygon and take the mean per pass."""
    from rasterio.features import geometry_mask

    transform = ds.odc.geobox.transform
    shape = (ds.sizes["y"], ds.sizes["x"])
    inside = ~geometry_mask(
        [geometry], out_shape=shape, transform=transform, invert=False
    )

    if inside.sum() == 0:
        raise ValueError(
            f"{field_id}: polygon covers no pixels. Either it falls outside the "
            f"bbox, or it is smaller than one {RESOLUTION_M} m pixel."
        )

    dates, vv_out, vh_out, counts = [], [], [], []
    for i in range(ds.sizes["time"]):
        vv = ds["vv"].isel(time=i).values[inside]
        vh = ds["vh"].isel(time=i).values[inside]
        n = int(np.isfinite(vv).sum() and (vv > 0).sum())
        if n < MIN_PIXELS:
            continue
        dates.append(pd.Timestamp(ds.time.values[i]).date())
        vv_out.append(mean_db(vv))
        vh_out.append(mean_db(vh))
        counts.append(n)

    return FieldSeries(field_id, dates, vv_out, vh_out, counts)


def field_bbox(geometry_wgs84, pad_m: float = 200.0) -> tuple:
    """A small WGS84 bbox around one field, padded so the polygon isn't clipped.

    200 m of padding is ~20 pixels — enough that the polygon sits comfortably
    inside the loaded window, cheap enough to be irrelevant to download size.
    """
    pad_deg = pad_m / 111_000.0
    minx, miny, maxx, maxy = geometry_wgs84.bounds
    return (minx - pad_deg, miny - pad_deg, maxx + pad_deg, maxy + pad_deg)


def series_for_fields(fields_wgs84, start: date, end: date, verbose: bool = True):
    """One field at a time: small cube, mask, mean. Yields FieldSeries.

    Per-field rather than one big cube, for three reasons: the download stays
    small, the cache keys on the field so re-running after adding one field
    re-fetches only that field, and a single bad polygon fails alone instead of
    taking the run with it.
    """
    from rich import print as rprint

    for _, row in fields_wgs84.iterrows():
        field_id = row["field_id"]
        try:
            ds = load_scenes(field_bbox(row.geometry), start, end)
            geom_utm = (
                fields_wgs84.loc[[row.name], "geometry"]
                .to_crs(CRS_UTM_44N)
                .iloc[0]
            )
            series = series_for_field(ds, geom_utm, field_id)
        except Exception as exc:  # one bad polygon must not kill the run
            if verbose:
                rprint(f"  [red]{field_id}: {exc}[/red]")
            continue

        if verbose:
            vv = np.array(series.vv_db)
            rprint(f"  {field_id}: {len(series.dates):>3} passes  "
                   f"VV {vv.min():>6.1f} … {vv.max():>6.1f} dB  "
                   f"median {np.median(vv):>6.1f}  "
                   f"{int(np.median(series.n_pixels))} px")
        yield series


app = typer.Typer(add_completion=False)


@app.command()
def main(
    field: str = typer.Option(None, help="One field id, e.g. F001. Omit for all."),
    season: str = typer.Option(None, help="2025 | 2026. Defaults to active_season."),
    include_preseason: bool = typer.Option(
        True, help="Also fetch the 180 days before the season, for SF_p."
    ),
) -> None:
    import geopandas as gpd
    from rich import print as rprint

    from src.config import FIELDS_GEOJSON

    if not FIELDS_GEOJSON.exists():
        rprint(f"[red]{FIELDS_GEOJSON} missing.[/red] Draw the polygons first — "
               f"geojson.io over satellite imagery, one per field.")
        raise typer.Exit(1)

    season = season or settings.active_season
    start = getattr(settings, f"season_{season}_start")
    end = getattr(settings, f"season_{season}_end")
    if include_preseason:
        start = settings.preseason_start if season == settings.active_season else start
    end = min(end, date.today())

    fields = gpd.read_file(FIELDS_GEOJSON).to_crs("EPSG:4326")
    if field:
        fields = fields[fields["field_id"] == field]
        if fields.empty:
            rprint(f"[red]No field {field}[/red]")
            raise typer.Exit(1)

    rprint(f"[bold]Sentinel-1 {COLLECTION}[/bold]  {len(fields)} field(s)  "
           f"{start} → {end}  orbit {settings.s1_orbit_direction}\n")

    frames = [s.to_frame() for s in series_for_fields(fields, start, end)]
    if not frames:
        rprint("[red]No field produced a series.[/red]")
        raise typer.Exit(1)

    out = pd.concat(frames, ignore_index=True)
    path = INTERIM_DIR / f"s1_series_{season}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path)
    rprint(f"\n[green]wrote {path}[/green]  {len(out)} field-date rows")
    rprint("[dim]Sanity: ponded -22…-17 dB, bare/drained ~-10 dB, "
           "peak rice canopy -16…-14 dB. If nothing goes below -16 dB, check the "
           "polygons before the threshold. If the season MAX sits above ~-14 dB, "
           "suspect the polygon is pulling in bund or road.[/dim]")


if __name__ == "__main__":
    app()
