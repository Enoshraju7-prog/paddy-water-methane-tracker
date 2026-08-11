"""SoilGrids (ISRIC) — soil organic carbon, clay, pH. Free, keyless.

Honest scoping note: **soil properties do not enter the v1 methane number.** The
IPCC Tier 2 rice equation has no soil term — it is EF_c × SF_w × SF_p × SF_o and
nothing else. So this module is here for two reasons only:

1. Context in the write-up ("these are heavy delta clays, which hold water").
2. The v4 roadmap item — RothC soil carbon needs SOC and clay as inputs.

Do not let it eat day-5 time. If you are behind, skip it entirely; it is above
RothC on the cut list for a reason.

Resolution is 250 m, so for a 0.4 ha field you are reading essentially one pixel.
Treat it as a regional descriptor, not a field measurement.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import requests

from src.config import SOILGRIDS_DIR
from src.data.cache import cache_key, cached_json

API = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# depth 0–30 cm, mean value. Conversion factors are SoilGrids' own — the API
# returns integers scaled to avoid floats.
PROPERTIES = {
    "soc": ("dg/kg", 10.0),      # → g/kg
    "clay": ("g/kg", 10.0),      # → %
    "phh2o": ("pH*10", 10.0),    # → pH
    "bdod": ("cg/cm3", 100.0),   # → g/cm3
}


def fetch_soil(fields: gpd.GeoDataFrame) -> pd.DataFrame:
    """One row per field with soil properties at its centroid, 0–30 cm."""
    rows = []
    for _, field in fields.iterrows():
        centroid = field.geometry.centroid
        rows.append(
            {
                "field_id": field["field_id"],
                **_query_point(centroid.y, centroid.x),
            }
        )
    return pd.DataFrame(rows)


def _query_point(lat: float, lon: float) -> dict:
    key = cache_key(lat=round(lat, 4), lon=round(lon, 4))
    path = SOILGRIDS_DIR / f"soilgrids_{key}.json"

    payload = cached_json(path, lambda: _download(lat, lon))
    return _parse(payload)


def _download(lat: float, lon: float) -> dict:
    response = requests.get(
        API,
        params=[
            ("lat", lat),
            ("lon", lon),
            *[("property", p) for p in PROPERTIES],
            ("depth", "0-30cm"),
            ("value", "mean"),
        ],
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def _parse(payload: dict) -> dict:
    out: dict[str, float | None] = {}
    for layer in payload.get("properties", {}).get("layers", []):
        name = layer["name"]
        if name not in PROPERTIES:
            continue
        _, divisor = PROPERTIES[name]
        depths = layer.get("depths", [])
        raw = depths[0]["values"]["mean"] if depths else None
        out[name] = raw / divisor if raw is not None else None
    return out
