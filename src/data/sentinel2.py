"""Sentinel-2 L2A — NDVI on clear days, for crop stage.

Secondary to the radar, and it will be sparse: this is a monsoon season and
optical imagery is under cloud most of the time. Expect a handful of usable
scenes across 150 days. That is fine — you are not tracking water with this.

What it is actually for: **knowing when the canopy closed.** Around 50–70 days
after transplanting the rice closes over and hides the water underneath, at
which point VV backscatter climbs even though the field is still flooded, and a
fixed radar threshold starts calling flooded fields dry. NDVI tells you when
that transition happened so you can either raise the threshold after it or, more
honestly, mark those observations as low-confidence.

    NDVI = (NIR − Red) / (NIR + Red) = (B08 − B04) / (B08 + B04)

Bare/flooded soil ≈ 0.1–0.2, closed rice canopy ≈ 0.7–0.85.
"""

from __future__ import annotations

from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import CRS_UTM_44N, S2_DIR, settings
from src.data.cache import cache_key, cached_frame

COLLECTION = "sentinel-2-l2a"
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
MAX_CLOUD_COVER = 30  # scene-level %, a coarse first filter


def fetch_ndvi(
    fields: gpd.GeoDataFrame,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Mean NDVI per field per clear date. Columns: field_id, date, ndvi, n_pixels."""
    start = start or settings.season_start
    end = end or settings.season_end

    key = cache_key(
        collection=COLLECTION,
        bbox=tuple(round(v, 4) for v in fields.total_bounds),
        start=start,
        end=end,
        cloud=MAX_CLOUD_COVER,
    )
    path = S2_DIR / f"ndvi_{key}.parquet"
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
    items = list(
        catalog.search(
            collections=[COLLECTION],
            bbox=list(gdf.total_bounds),
            datetime=f"{start}/{end}",
            query={"eo:cloud_cover": {"lt": MAX_CLOUD_COVER}},
        ).items()
    )
    if not items:
        # Entirely expected during monsoon. Not an error — return empty and
        # let the caller carry on without a crop-stage layer.
        return pd.DataFrame(columns=["field_id", "date", "ndvi", "n_pixels"])

    cube = odc.stac.load(
        items,
        bands=("B04", "B08", "SCL"),
        crs=CRS_UTM_44N,
        resolution=10,
        bbox=list(gdf.total_bounds),
        chunks={},
        groupby="solar_day",
    )

    # Scene-level cloud cover is not enough — a 20%-cloudy scene can still be
    # fully clouded over your particular field. SCL is the per-pixel scene
    # classification: 4 = vegetation, 5 = bare soil, 6 = water. Everything else
    # (cloud, shadow, cirrus, snow, saturated) gets dropped.
    valid = cube["SCL"].isin([4, 5, 6])
    red = cube["B04"].where(valid).astype("float32")
    nir = cube["B08"].where(valid).astype("float32")
    ndvi = (nir - red) / (nir + red)

    projected = gdf.to_crs(CRS_UTM_44N)
    transform = cube.odc.geobox.transform
    shape = (cube.sizes["y"], cube.sizes["x"])
    dates = pd.to_datetime(cube.time.values).date

    rows: list[dict] = []
    for _, field in tqdm(projected.iterrows(), total=len(projected), desc="ndvi"):
        mask = geometry_mask(
            [field.geometry], out_shape=shape, transform=transform, invert=True
        )
        if not mask.any():
            continue

        masked = ndvi.where(mask)
        means = masked.mean(dim=("y", "x")).compute().values
        counts = masked.notnull().sum(dim=("y", "x")).compute().values

        for d, value, count in zip(dates, means, counts, strict=True):
            # Fewer than half the pixels clear → don't trust the field mean.
            if not np.isfinite(value) or count < mask.sum() * 0.5:
                continue
            rows.append(
                {
                    "field_id": field["field_id"],
                    "date": d,
                    "ndvi": float(value),
                    "n_pixels": int(count),
                }
            )

    return pd.DataFrame(rows).sort_values(["field_id", "date"]).reset_index(drop=True)
