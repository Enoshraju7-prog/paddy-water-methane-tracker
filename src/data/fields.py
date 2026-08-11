"""Field boundaries — load, validate, and measure.

The boundaries come from you: walked with a phone GPS, or drawn in QGIS over a
satellite basemap using landmarks the farmer points out. Slow, manual and
unglamorous — and exactly what "aggregating fragmented smallholdings" means in
practice.

Expected schema for `data/fields/fields.geojson` (EPSG:4326):

    field_id              str    "F001" — anonymous, stable, no names, no survey numbers
    farmer_id             str    "Farmer 1" — anonymous
    village_code          str    "V1" — anonymous
    transplant_date       date   from the interview; drives `t` in the IPCC equation
    harvest_date          date   from the interview
    straw_management      str    see ORGANIC_AMENDMENT choices in src/models/ipcc.py
    days_before_flooding  int    days between straw incorporation and flooding (<30 matters a lot)
    controls_irrigation   bool   can he actually choose when to water? Often canal schedule decides.
    notes                 str    free text, no identifying detail
"""

from __future__ import annotations

import geopandas as gpd

from src.config import CRS_UTM_44N, CRS_WGS84, FIELDS_GEOJSON

REQUIRED_COLUMNS = ["field_id", "farmer_id"]


def load_fields(path=None) -> gpd.GeoDataFrame:
    """Load field polygons in WGS84, with an `area_ha` column measured in UTM 44N.

    Area is computed after reprojecting to EPSG:32644. Computing area on
    lat/lon coordinates gives you square degrees, which is not a unit of area —
    it is the single most common beginner mistake in geospatial work.
    """
    path = path or FIELDS_GEOJSON
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Field boundaries come from field visit 1 — "
            f"see docs/02-field-visit-kit.md. For plumbing work before the visit, "
            f"use data/fields/fields.sample.geojson."
        )

    gdf = gpd.read_file(path)

    missing = [c for c in REQUIRED_COLUMNS if c not in gdf.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")

    if gdf.crs is None:
        raise ValueError(f"{path} has no CRS. Write it as EPSG:4326.")
    gdf = gdf.to_crs(CRS_WGS84)

    invalid = gdf[~gdf.geometry.is_valid]
    if len(invalid):
        # Self-intersecting polygons are common from hand-drawn QGIS work.
        gdf["geometry"] = gdf.geometry.buffer(0)

    gdf["area_ha"] = gdf.to_crs(CRS_UTM_44N).area / 10_000.0

    duplicates = gdf["field_id"][gdf["field_id"].duplicated()].tolist()
    if duplicates:
        raise ValueError(f"duplicate field_id values: {duplicates}")

    return gdf


def total_bbox(gdf: gpd.GeoDataFrame, pad_deg: float = 0.01) -> tuple[float, ...]:
    """Padded WGS84 bounding box covering every field — the STAC search extent."""
    min_lon, min_lat, max_lon, max_lat = gdf.total_bounds
    return (min_lon - pad_deg, min_lat - pad_deg, max_lon + pad_deg, max_lat + pad_deg)


def jitter_for_publication(
    gdf: gpd.GeoDataFrame, metres: float = 500.0
) -> gpd.GeoDataFrame:
    """Displace every polygon by a fixed random offset, for the public repo.

    Preserves shape and relative geometry (useful for a demo map) while making
    the fields non-locatable. Run this before committing anything derived from
    real boundaries; see the privacy section of the README.
    """
    import numpy as np

    projected = gdf.to_crs(CRS_UTM_44N).copy()
    rng = np.random.default_rng(seed=42)  # deterministic: same jitter every run
    dx, dy = rng.uniform(-metres, metres, size=2)
    projected["geometry"] = projected.geometry.translate(xoff=dx, yoff=dy)
    return projected.to_crs(CRS_WGS84)
