"""Single source of truth for paths, CRS, thresholds and model constants.

Everything tunable lives here or in `.env`. If you find a magic number anywhere
else in `src/`, it belongs in this file.

    python -m src.config      # prints the resolved config, sanity check
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
FIELDS_DIR = DATA_DIR / "fields"

S1_DIR = RAW_DIR / "sentinel1"
S2_DIR = RAW_DIR / "sentinel2"
POWER_DIR = RAW_DIR / "power"
SOILGRIDS_DIR = RAW_DIR / "soilgrids"

FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"
MODELS_DIR = PROJECT_ROOT / "models"

# The one file the whole pipeline hangs off. Anonymised: `field_id`, no names.
FIELDS_GEOJSON = FIELDS_DIR / "fields.geojson"


# ─────────────────────────────────────────────────────────────────────────────
# Coordinate reference systems
# ─────────────────────────────────────────────────────────────────────────────

# Storage / interchange / anything that talks to a web map.
CRS_WGS84 = "EPSG:4326"

# UTM zone 44N — the projected CRS for the East Godavari region.
# ALL area, distance and buffer computation happens here. You cannot measure
# hectares in degrees: a degree of longitude is ~110 km at the equator and 0 km
# at the pole, so "area in square degrees" is not a unit of anything.
CRS_UTM_44N = "EPSG:32644"


class Settings(BaseSettings):
    """Environment-overridable settings. See `.env.example`."""

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    # ── Study area ───────────────────────────────────────────────────────────
    # Bounding box for the study mandals, WGS84: (min_lon, min_lat, max_lon, max_lat).
    # Placeholder covers part of the East Godavari delta — REPLACE after field visit 1
    # with the actual extent of your polygons.
    bbox_min_lon: float = 81.70
    bbox_min_lat: float = 16.60
    bbox_max_lon: float = 82.10
    bbox_max_lat: float = 16.95

    # ── Season windows ───────────────────────────────────────────────────────
    # Kharif (monsoon) paddy in East Godavari. Confirm both dates with farmers —
    # transplanting date drives `t` in the IPCC equation and it varies by field.
    season_start: date = date(2025, 6, 15)
    season_end: date = date(2025, 11, 15)

    # Pre-season lookback for SF_p. IPCC defines the pre-season as the 180 days
    # before cultivation, so we pull radar for that window too. Cheap, and SF_p
    # can be 2.41 — a big lever to leave on the table.
    preseason_days: int = 180

    # ── Sentinel-1 flood detection ───────────────────────────────────────────
    # Open water is a specular reflector: it bounces the pulse away from the
    # satellite, so flooded pixels come back dark. Typical σ⁰ VV values:
    #   open water  ~ -18 dB   |   bare soil ~ -10 dB   |   dense canopy ~ -7 dB
    # -16 dB is a defensible starting threshold. It is a STARTING point — tune it
    # against farmer recall on day 8 and record what you changed and why.
    s1_vv_flood_threshold_db: float = -16.0

    # Secondary signal. Once the canopy closes (~60 days after transplant) the
    # rice hides the water and VV climbs even though the field is still flooded.
    # VH/VV ratio degrades more slowly under canopy — use it as a cross-check.
    s1_use_vh_ratio: bool = True

    # Orbit consistency matters: backscatter differs between ascending and
    # descending passes and between relative orbits. Mixing them injects steps
    # into the time series that look like drying events. Pin one.
    s1_orbit_direction: str = "descending"  # "ascending" | "descending" | "any"

    # ── Season metrics ───────────────────────────────────────────────────────
    # Minimum consecutive dry observations to count as a drying event. With a
    # 12-day revisit, 1 observation ≈ up to 12 days dry. Keep at 1 for v1 and
    # say plainly that the count is a lower bound.
    min_obs_for_drying_event: int = 1

    # ── Methane model ────────────────────────────────────────────────────────
    # IPCC 2019 Refinement Vol.4 Ch.5 Table 5.11. Range 0.80 – 1.76.
    ef_c_baseline: float = 1.19  # kg CH4 ha^-1 day^-1

    # AR6 GWP100 for non-fossil (biogenic) methane. AR5 was 28, AR4 was 25.
    # Whichever you use, print it on the season card.
    gwp_ch4: float = 27.0

    # Default cultivation period if a farmer's transplant/harvest dates are
    # missing. Per-field values from interviews always win.
    default_cultivation_days: int = 120

    # ── Water & pumping (all placeholders — replace with Visit 1 numbers) ─────
    awd_water_saving_low: float = 0.25   # AWD saves roughly 25–35% of irrigation
    awd_water_saving_high: float = 0.35
    seasonal_irrigation_mm: float = 1200.0     # mm applied over the season
    pump_discharge_m3_per_hour: float = 40.0   # a typical 5 HP centrifugal pump
    cost_per_pump_hour_inr: float = 60.0       # diesel. Set to ~0 for subsidised power.

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+psycopg://varaha:varaha@localhost:5432/varaha"
    )

    # ── Behaviour ────────────────────────────────────────────────────────────
    # Never re-download. Every fetch checks the cache first.
    use_cache: bool = True

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (
            self.bbox_min_lon,
            self.bbox_min_lat,
            self.bbox_max_lon,
            self.bbox_max_lat,
        )

    @property
    def preseason_start(self) -> date:
        from datetime import timedelta

        return self.season_start - timedelta(days=self.preseason_days)


settings = Settings()


def ensure_dirs() -> None:
    """Create every directory the pipeline writes to."""
    for path in (
        RAW_DIR, S1_DIR, S2_DIR, POWER_DIR, SOILGRIDS_DIR,
        INTERIM_DIR, PROCESSED_DIR, FIELDS_DIR, FIGURES_DIR, MODELS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    from rich import print as rprint

    ensure_dirs()
    rprint("[bold]Paddy Water & Methane Tracker — config[/bold]\n")
    rprint(f"  project root      {PROJECT_ROOT}")
    rprint(f"  storage CRS       {CRS_WGS84}")
    rprint(f"  measurement CRS   {CRS_UTM_44N}  (area/distance ONLY here)")
    rprint(f"  bbox              {settings.bbox}")
    rprint(f"  pre-season        {settings.preseason_start} → {settings.season_start}")
    rprint(f"  season            {settings.season_start} → {settings.season_end}")
    rprint(f"  flood threshold   {settings.s1_vv_flood_threshold_db} dB (VV)")
    rprint(f"  orbit             {settings.s1_orbit_direction}")
    rprint(f"  EF_c              {settings.ef_c_baseline} kg CH4/ha/day")
    rprint(f"  GWP100 CH4        {settings.gwp_ch4}")
    rprint(f"  fields file       {FIELDS_GEOJSON}  "
           f"[{'found' if FIELDS_GEOJSON.exists() else 'MISSING — field visit 1'}]")
    rprint("\n[green]directories ready[/green]")
