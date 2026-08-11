"""Sentinel-1 GRD backscatter — the core signal of the whole project.

Radar, not optical, because the season is the monsoon and optical imagery will
be under cloud for most of it. Microwaves pass through cloud and work at night.

Open water is a *specular* reflector: it is smooth at the radar wavelength, so
it mirrors the pulse away from the satellite instead of scattering some of it
back. A flooded field therefore comes back dark.

    open water   σ⁰ VV  ≈ −18 dB
    bare soil    σ⁰ VV  ≈ −10 dB
    dense canopy σ⁰ VV  ≈  −7 dB

Product: `sentinel-1-rtc` on Microsoft Planetary Computer — radiometrically
terrain-corrected, already in γ⁰ power units, already orthorectified. Use it in
preference to raw `sentinel-1-grd`: it removes a whole class of terrain and
incidence-angle artefacts you would otherwise have to correct yourself.

Output: one row per (field_id, date) with mean VV and VH in dB.
"""

from __future__ import annotations

from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import CRS_UTM_44N, S1_DIR, settings
from src.data.cache import cache_key, cached_frame

COLLECTION = "sentinel-1-rtc"
BANDS = ("vv", "vh")
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def fetch_backscatter(
    fields: gpd.GeoDataFrame,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Mean VV/VH backscatter per field per acquisition date.

    Returns columns: field_id, date, vv_db, vh_db, vh_vv_ratio, n_pixels, orbit.

    Cached to `data/raw/sentinel1/`. Rerunning is free.
    """
    start = start or settings.preseason_start
    end = end or settings.season_end

    key = cache_key(
        collection=COLLECTION,
        bbox=tuple(round(v, 4) for v in fields.total_bounds),
        start=start,
        end=end,
        orbit=settings.s1_orbit_direction,
        n_fields=len(fields),
    )
    path = S1_DIR / f"backscatter_{key}.parquet"
    return cached_frame(path, lambda: _download(fields, start, end))


def _download(gdf: gpd.GeoDataFrame, start: date, end: date) -> pd.DataFrame:
    import odc.stac
    import planetary_computer
    import pystac_client
    from rasterio.features import geometry_mask
    from tqdm import tqdm

    catalog = pystac_client.Client.open(
        STAC_URL, modifier=planetary_computer.sign_inplace
    )

    search = catalog.search(
        collections=[COLLECTION],
        bbox=list(gdf.total_bounds),
        datetime=f"{start}/{end}",
    )
    items = list(search.items())

    # Pin one orbit direction. Backscatter differs systematically between
    # ascending and descending passes (different look geometry), and mixing
    # them injects steps into the time series that look exactly like drying
    # events. This is a real trap — one of the easiest ways to fabricate a
    # drying event that never happened.
    if settings.s1_orbit_direction != "any":
        items = [
            it
            for it in items
            if it.properties.get("sat:orbit_state") == settings.s1_orbit_direction
        ]

    if not items:
        raise RuntimeError(
            f"no {COLLECTION} items for bbox {gdf.total_bounds} "
            f"{start}→{end} orbit={settings.s1_orbit_direction}. "
            f"Try s1_orbit_direction='any' to check coverage."
        )

    # Load lazily at 10 m in UTM 44N. Small fields — a 20 m or 30 m resolution
    # would leave only a handful of pixels inside a 0.4 ha plot.
    cube = odc.stac.load(
        items,
        bands=BANDS,
        crs=CRS_UTM_44N,
        resolution=10,
        bbox=list(gdf.total_bounds),
        chunks={},
        groupby="solar_day",
    )

    projected = gdf.to_crs(CRS_UTM_44N)
    transform = cube.odc.geobox.transform
    shape = (cube.sizes["y"], cube.sizes["x"])

    rows: list[dict] = []
    for _, field in tqdm(
        projected.iterrows(), total=len(projected), desc="fields"
    ):
        # `invert=True` → True *inside* the polygon, which is what we want to keep.
        mask = geometry_mask(
            [field.geometry], out_shape=shape, transform=transform, invert=True
        )
        if not mask.any():
            # Sub-pixel field, or a polygon outside the loaded extent.
            continue

        clipped = cube.where(mask)
        vv = clipped["vv"].mean(dim=("y", "x")).compute().values
        vh = clipped["vh"].mean(dim=("y", "x")).compute().values
        dates = pd.to_datetime(cube.time.values).date

        for d, vv_lin, vh_lin in zip(dates, vv, vh, strict=True):
            if not np.isfinite(vv_lin) or vv_lin <= 0:
                continue
            rows.append(
                {
                    "field_id": field["field_id"],
                    "date": d,
                    "vv_db": to_db(vv_lin),
                    "vh_db": to_db(vh_lin) if np.isfinite(vh_lin) and vh_lin > 0 else np.nan,
                    "n_pixels": int(mask.sum()),
                    "orbit": settings.s1_orbit_direction,
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("no valid pixels for any field — check CRS and polygons")

    frame["vh_vv_ratio"] = frame["vh_db"] - frame["vv_db"]  # dB difference = ratio
    return frame.sort_values(["field_id", "date"]).reset_index(drop=True)


def to_db(linear: float | np.ndarray) -> float | np.ndarray:
    """Linear power (γ⁰) → decibels.

    Average in LINEAR space, then convert — never average dB values. dB is a
    logarithm, so the mean of dB is a geometric mean of power, which is not
    what you want and biases low. That is why the averaging above happens on
    the raw cube and this conversion happens last.
    """
    return 10.0 * np.log10(linear)


def to_linear(db: float | np.ndarray) -> float | np.ndarray:
    return 10.0 ** (db / 10.0)
