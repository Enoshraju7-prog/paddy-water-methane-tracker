"""NASA POWER — daily rainfall and temperature. Free, keyless, no registration.

Two jobs in this project:

1. **Sanity-checking flood detection.** A field that the radar says went dry
   during a week of 80 mm rainfall deserves a second look. Rain is your cheapest
   independent check on day 7.
2. **Context for the write-up.** "The 2025 kharif season had a 3-week dry spell
   in September" is the kind of sentence that makes a validation note credible.

Resolution is ~0.5°, so this is regional weather, not field weather. One series
for the whole study area is the right granularity.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests

from src.config import POWER_DIR, settings
from src.data.cache import cache_key, cached_frame

API = "https://power.larc.nasa.gov/api/temporal/daily/point"

PARAMETERS = {
    "PRECTOTCORR": "precip_mm",       # bias-corrected total precipitation
    "T2M": "temp_c",                  # mean 2 m air temperature
    "T2M_MAX": "temp_max_c",
    "T2M_MIN": "temp_min_c",
    "RH2M": "humidity_pct",
}


def fetch_weather(
    lat: float | None = None,
    lon: float | None = None,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Daily weather for the study-area centroid. Columns: date + PARAMETERS values."""
    min_lon, min_lat, max_lon, max_lat = settings.bbox
    lat = lat if lat is not None else (min_lat + max_lat) / 2
    lon = lon if lon is not None else (min_lon + max_lon) / 2
    start = start or settings.preseason_start
    end = end or settings.season_end

    key = cache_key(lat=round(lat, 3), lon=round(lon, 3), start=start, end=end)
    path = POWER_DIR / f"power_{key}.parquet"
    return cached_frame(path, lambda: _download(lat, lon, start, end))


def _download(lat: float, lon: float, start: date, end: date) -> pd.DataFrame:
    response = requests.get(
        API,
        params={
            "parameters": ",".join(PARAMETERS),
            "community": "AG",
            "latitude": lat,
            "longitude": lon,
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()["properties"]["parameter"]

    frame = pd.DataFrame({name: payload[code] for code, name in PARAMETERS.items()})
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    frame = frame.rename_axis("date").reset_index()

    # POWER uses -999 as its fill value. Left in place it will quietly turn
    # your seasonal rainfall total into a large negative number.
    return frame.replace(-999.0, pd.NA)
