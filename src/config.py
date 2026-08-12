"""Single source of truth for paths, CRS, seasons, thresholds and model constants.

Everything tunable lives here or in `.env`. If you find a magic number anywhere
else in `src/`, it belongs in this file.

    python -m src.config      # print the resolved config, sanity check
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
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

# Validation results are TRACKED, unlike everything else under data/. They carry
# no coordinates and no personal detail — only field ids and measurements — and a
# claim about accuracy is worthless if the reader cannot see the rows behind it.
VALIDATION_DIR = DATA_DIR / "validation"

S1_DIR = RAW_DIR / "sentinel1"
S2_DIR = RAW_DIR / "sentinel2"
POWER_DIR = RAW_DIR / "power"
SOILGRIDS_DIR = RAW_DIR / "soilgrids"

FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"
MODELS_DIR = PROJECT_ROOT / "models"

# reports/figures/ is gitignored (regenerated output). Figures that a reader of
# the README needs to see are written here instead, and are tracked.
DOCS_IMG_DIR = PROJECT_ROOT / "docs" / "img"

FIELDS_GEOJSON = FIELDS_DIR / "fields.geojson"
GROUND_TRUTH_CSV = FIELDS_DIR / "ground_truth.csv"
INTERVIEWS_CSV = FIELDS_DIR / "interviews.csv"


# ─────────────────────────────────────────────────────────────────────────────
# Coordinate reference systems — the two-CRS rule
# ─────────────────────────────────────────────────────────────────────────────

# Storage, interchange, anything that talks to a web map.
CRS_WGS84 = "EPSG:4326"

# UTM zone 44N — the projected CRS for the East Godavari region.
# ALL area, distance and buffer computation happens here. Measuring area in
# degrees is off by ~11 billion times: a degree of longitude is ~111 km at the
# equator and 0 km at the pole, so square degrees are not a fixed size.
CRS_UTM_44N = "EPSG:32644"


class Settings(BaseSettings):
    """Environment-overridable settings. See `.env.example`."""

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    # ── Study area ───────────────────────────────────────────────────────────
    # WGS84 bbox: (min_lon, min_lat, max_lon, max_lat).
    #
    # East Godavari delta, north-east corner: the Kakinada–Pithapuram side plus
    # the Ramachandrapuram/Mandapeta paddy belt to the west. Anchors named for
    # Trip 1, roughly:
    #
    #   Pithapuram          17.12 N  82.25 E   (northern edge)
    #   Vakada              17.12 N  82.28 E   (Gollaprolu side, near Pithapuram)
    #   Sarpavaram          17.02 N  82.22 E   (Kakinada Rural)
    #   Kakinada            16.99 N  82.25 E   (eastern edge — coast at ~82.28)
    #   Ramachandrapuram    16.83 N  82.03 E
    #   Mandapeta           16.87 N  81.93 E   (western edge)
    #
    # "Kothuru" and "Sandipudi" are common village names in this belt and are
    # inside the envelope; fix their exact locations from the Trip 1 GPS traces.
    #
    # ~50 × 50 km. Wide enough that several relative orbits may cover it, which
    # helps the overpass calendar. Tighten it once fields.geojson exists —
    # Phase 2 should replace this with the polygon envelope plus a small buffer.
    bbox_min_lon: float = 81.85
    bbox_min_lat: float = 16.75
    bbox_max_lon: float = 82.32
    bbox_max_lat: float = 17.20

    # ── Seasons ──────────────────────────────────────────────────────────────
    # Two seasons, two jobs:
    #   2025 is COMPLETE — it builds and tests the pipeline.
    #   2026 is LIVE     — it supplies same-day validation.
    # Confirm both against farmer transplanting dates; they vary field to field.
    season_2025_start: date = date(2025, 6, 15)
    season_2025_end: date = date(2025, 11, 15)
    season_2026_start: date = date(2026, 6, 15)
    season_2026_end: date = date(2026, 11, 15)

    # Which season the pipeline treats as primary.
    active_season: str = "2025"

    # IPCC defines the pre-season as the 180 days before cultivation. Pulling
    # radar for that window too is cheap, and SF_p can be 2.41 — a large lever
    # to leave on the table.
    preseason_days: int = 180

    # ── Sentinel-1 flood detection ───────────────────────────────────────────
    # Open water is a specular reflector — it mirrors the pulse away from the
    # satellite, so flooded pixels come back dark. Typical σ⁰ VV for RICE:
    #   ponded paddy  -22 … -17 dB
    #   bare/drained  ~ -10 dB
    #   peak canopy   -16 … -14 dB   <-- NOT -7 dB
    #
    # That last line is the one that matters and the one most tables get wrong
    # for this crop. "Dense canopy ~ -7 dB" is a forest figure. A rice canopy
    # stands in water, which keeps scattering the pulse away after the leaves
    # close, so peak-season VV lands far lower — sometimes barely 1 dB above the
    # threshold below rather than the ~9 dB that -7 dB would imply.
    #
    # So -16.0 is a defensible STARTING point with LESS headroom than it looks
    # like it has. Tune it against the Phase 5 same-day observations via
    # sweep_threshold(), and record what you changed and why. If a field's
    # series peaks within ~2 dB of this value, its mid-season observations are
    # low-confidence by construction — flag them, don't move the threshold to
    # make the curve look right (rule 6).
    s1_vv_flood_threshold_db: float = -16.0

    # Backscatter differs between ascending and descending passes. Mixing them
    # injects steps into the time series that look like drying events. Pin one.
    s1_orbit_direction: str = "descending"  # "ascending" | "descending" | "any"

    # ── VH-drop flood rule ───────────────────────────────────────────────────
    # Measured 12 Aug 2026, 12 locations photographed 15 minutes after the pass,
    # every one holding 5-7 cm of water: the absolute VV rule above scored 0/12.
    # A rice field flooded UNDER a canopy is not dark, so "how low is it" is the
    # wrong question. "How far has it fallen from its own dry level" is the right
    # one, and VH falls much further than VV when the crop floods.
    #
    # Two things this buys, beyond accuracy:
    #   - a per-field reference absorbs whatever makes one field sit brighter
    #     than its neighbour: soil, roughness, row direction, look angle.
    #   - a DIFFERENCE cancels any constant calibration offset, so a sigma0
    #     baseline and a gamma0 observation can be compared. An absolute
    #     threshold cannot survive that mix; this rule can.
    #
    # 3.0 dB is a STARTING point, not a result. Sweep it — src/features/flooding.py.
    vh_drop_threshold_db: float = 3.0

    # The dry reference window: this many days before season_start. It must land
    # on bare soil, so check the curves before trusting it. NOTE the 2026 curves
    # say transplanting happens mid-JULY, not at season_start (15 June) — so this
    # window is currently wider than it looks. Fix season_start first.
    baseline_days: int = 90

    # A field needs at least this many reference passes for a usable baseline.
    min_baseline_obs: int = 3

    # ── Season metrics ───────────────────────────────────────────────────────
    # Minimum consecutive dry observations to count as a drying event. At a
    # ~12-day revisit, 1 observation ≈ up to 12 days dry. Keep at 1 for v1 and
    # say plainly that the resulting count is a lower bound.
    min_obs_for_drying_event: int = 1

    # ── Methane model ────────────────────────────────────────────────────────
    ef_c_baseline: float = 1.19   # IPCC 2019 Table 5.11, kg CH4 ha^-1 day^-1
    gwp_ch4: float = 27.0         # AR6 GWP100, non-fossil methane
    default_cultivation_days: int = 120

    # ── Water & pumping — placeholders until Trip 1 ──────────────────────────
    awd_water_saving_low: float = 0.25
    awd_water_saving_high: float = 0.35
    seasonal_irrigation_mm: float = 1200.0
    pump_discharge_m3_per_hour: float = 40.0
    cost_per_pump_hour_inr: float = 60.0

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg://varaha:varaha@localhost:5432/varaha"

    # ── Behaviour ────────────────────────────────────────────────────────────
    use_cache: bool = True

    # ── Derived ──────────────────────────────────────────────────────────────

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.bbox_min_lon, self.bbox_min_lat,
                self.bbox_max_lon, self.bbox_max_lat)

    @property
    def centroid(self) -> tuple[float, float]:
        """(lat, lon) of the study area — for point APIs like NASA POWER."""
        return ((self.bbox_min_lat + self.bbox_max_lat) / 2,
                (self.bbox_min_lon + self.bbox_max_lon) / 2)

    @property
    def season_start(self) -> date:
        return getattr(self, f"season_{self.active_season}_start")

    @property
    def season_end(self) -> date:
        return getattr(self, f"season_{self.active_season}_end")

    @property
    def preseason_start(self) -> date:
        return self.season_start - timedelta(days=self.preseason_days)


settings = Settings()


def ensure_dirs() -> None:
    """Create every directory the pipeline writes to."""
    for path in (RAW_DIR, S1_DIR, S2_DIR, POWER_DIR, SOILGRIDS_DIR,
                 INTERIM_DIR, PROCESSED_DIR, FIELDS_DIR, VALIDATION_DIR,
                 FIGURES_DIR, DOCS_IMG_DIR, MODELS_DIR):
        path.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    from rich import print as rprint

    ensure_dirs()
    rprint("[bold]Paddy Water & Methane Tracker — config[/bold]\n")
    rprint(f"  project root      {PROJECT_ROOT}")
    rprint(f"  storage CRS       {CRS_WGS84}")
    rprint(f"  measurement CRS   {CRS_UTM_44N}   [dim]area/distance ONLY here[/dim]")
    rprint(f"  bbox              {settings.bbox}")
    rprint(f"  centroid          {settings.centroid}")
    rprint()
    rprint(f"  active season     [bold]{settings.active_season}[/bold]")
    rprint(f"  pre-season        {settings.preseason_start} → {settings.season_start}")
    rprint(f"  season            {settings.season_start} → {settings.season_end}")
    rprint(f"  2026 (live)       {settings.season_2026_start} → {settings.season_2026_end}")
    rprint()
    rprint(f"  flood threshold   {settings.s1_vv_flood_threshold_db} dB (VV)")
    rprint(f"  orbit             {settings.s1_orbit_direction}")
    rprint(f"  EF_c              {settings.ef_c_baseline} kg CH4/ha/day")
    rprint(f"  GWP100 CH4        {settings.gwp_ch4}")
    rprint()
    status = "found" if FIELDS_GEOJSON.exists() else "MISSING — comes from Trip 1"
    rprint(f"  fields            {FIELDS_GEOJSON.name}  [{status}]")
    status = "found" if GROUND_TRUTH_CSV.exists() else "MISSING — comes from Trip 2+"
    rprint(f"  ground truth      {GROUND_TRUTH_CSV.name}  [{status}]")
    rprint("\n[green]directories ready[/green]")
