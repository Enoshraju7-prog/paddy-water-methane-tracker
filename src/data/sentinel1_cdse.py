"""Same-day Sentinel-1 backscatter from Copernicus Data Space (CDSE).

Why a second source at all. `sentinel1.py` reads Microsoft Planetary Computer,
which is anonymous and free but MIRRORS the ESA archive rather than being it.
Measured on 12 Aug 2026: the pass was acquired 00:22 UTC and was Online in the
CDSE catalogue the same morning, while Planetary Computer still had nothing
newer than 31 July more than five hours later. For the 2026 season the entire
point is *same-day* ground truth, so a lag of a day or two is not acceptable.

So: CDSE for today, Planetary Computer for the archive. Use the RTC series as
the record of truth and treat a CDSE reading as PROVISIONAL until RTC lands.

Two things make CDSE numbers NOT directly comparable to `sentinel1.py`:

  1. Sentinel Hub offers GAMMA0_TERRAIN, not terrain-corrected sigma0. At this
     latitude's incidence angle gamma0 reads roughly 1 dB brighter than sigma0
     (gamma0 = sigma0 / cos(theta)). Do not compare the two to one decimal.
  2. It is computed from GRD, not the RTC product.

Both differences are small next to the 3-8 dB gap this project is chasing, but
they are real. Record which source a number came from.

Credentials. CDSE is free; the OAuth client is created from the dashboard at
https://shapps.dataspace.copernicus.eu/dashboard/ under "User settings". Put
the two values in `.env`:

    CDSE_CLIENT_ID=...
    CDSE_CLIENT_SECRET=...

    python -m src.data.sentinel1_cdse --date 2026-08-12
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import typer
from shapely.geometry import Point

from src.config import CRS_UTM_44N, CRS_WGS84, FIELDS_DIR, settings

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)
STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

PHOTOLOG = FIELDS_DIR / "photolog-2026-08-12.csv"
OUT_CSV = FIELDS_DIR / "s1-cdse-same-day.csv"

# Ask for linear power and average it in linear power. Converting each pixel to
# dB first and taking the mean of the dB values biases every field mean, because
# sigma-nought is logarithmic. This is the single easiest way to be quietly wrong.
EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["VV", "VH", "dataMask"] }],
    output: [
      { id: "vv", bands: 1, sampleType: "FLOAT32" },
      { id: "vh", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(s) {
  return { vv: [s.VV], vh: [s.VH], dataMask: [s.dataMask] };
}
"""

app = typer.Typer(add_completion=False)


def get_token(client_id: str, client_secret: str) -> str:
    r = requests.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials",
              "client_id": client_id,
              "client_secret": client_secret},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def stats_for_geometry(token: str, geometry, day: date) -> dict | None:
    """Mean linear VV/VH over one polygon for one day, or None if no pass."""
    body = {
        "input": {
            "bounds": {
                "geometry": json.loads(gpd.GeoSeries([geometry],
                                                     crs=CRS_WGS84).to_json())
                            ["features"][0]["geometry"],
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [{
                "type": "sentinel-1-grd",
                "dataFilter": {
                    "acquisitionMode": "IW",
                    "polarization": "DV",
                    "resolution": "HIGH",
                    # Same trap as the archive path: mixing ascending and
                    # descending injects steps that look like drying events.
                    "orbitDirection": settings.s1_orbit_direction.upper(),
                },
                "processing": {
                    "backCoeff": "GAMMA0_TERRAIN",
                    "orthorectify": True,
                    "demInstance": "COPERNICUS",
                },
            }],
        },
        "aggregation": {
            "timeRange": {"from": f"{day}T00:00:00Z",
                          "to": f"{day + timedelta(days=1)}T00:00:00Z"},
            "aggregationInterval": {"of": "P1D"},
            "resx": 10, "resy": 10,
            "evalscript": EVALSCRIPT,
        },
    }
    r = requests.post(STATS_URL, json=body, timeout=180,
                      headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    intervals = [i for i in r.json().get("data", []) if "outputs" in i]
    return intervals[0] if intervals else None


def to_db(linear: float) -> float:
    return float(10.0 * np.log10(linear))


@app.command()
def main(
    day: str = typer.Option(..., "--date", help="pass date, YYYY-MM-DD"),
    half_m: float = typer.Option(25.0, help="half-width of the box, metres"),
) -> None:
    cid = os.getenv("CDSE_CLIENT_ID")
    secret = os.getenv("CDSE_CLIENT_SECRET")
    if not cid or not secret:
        raise typer.BadParameter(
            "CDSE_CLIENT_ID / CDSE_CLIENT_SECRET missing from .env — create an "
            "OAuth client at https://shapps.dataspace.copernicus.eu/dashboard/"
        )

    log = pd.read_csv(PHOTOLOG, comment="#")
    cent = log.groupby("cluster").agg(lat=("lat", "mean"),
                                      lon=("lon", "mean")).reset_index()

    # Two-CRS rule: buffer in UTM 44N, hand WGS84 to the API.
    g = gpd.GeoDataFrame(
        cent, geometry=[Point(r.lon, r.lat) for r in cent.itertuples()],
        crs=CRS_WGS84)
    g = g.assign(geometry=g.to_crs(CRS_UTM_44N)
                 .buffer(half_m, cap_style=3).to_crs(CRS_WGS84))

    token = get_token(cid, secret)
    target = date.fromisoformat(day)

    rows = []
    for r in g.itertuples():
        got = stats_for_geometry(token, r.geometry, target)
        if got is None:
            typer.echo(f"  {r.cluster}: no {settings.s1_orbit_direction} pass")
            continue
        out = got["outputs"]
        vv = out["vv"]["bands"]["B0"]["stats"]
        vh = out["vh"]["bands"]["B0"]["stats"]
        rows.append({"field_id": r.cluster, "date": day,
                     "vv_db": round(to_db(vv["mean"]), 2),
                     "vh_db": round(to_db(vh["mean"]), 2),
                     "n_pixels": vv["sampleCount"] - vv["noDataCount"],
                     "source": "cdse-gamma0-terrain"})
        typer.echo(f"  {r.cluster}: VV {rows[-1]['vv_db']:>7.2f} dB   "
                   f"VH {rows[-1]['vh_db']:>7.2f} dB")

    if not rows:
        typer.echo("nothing returned — check the date has a descending pass")
        raise typer.Exit(1)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)

    thr = settings.s1_vv_flood_threshold_db
    n_dry = int((df.vv_db > thr).sum())
    typer.echo(f"\nwrote {OUT_CSV}")
    typer.echo(f"{n_dry} of {len(df)} above the {thr:g} dB threshold "
               f"— the rule calls those dry.")


if __name__ == "__main__":
    app()
