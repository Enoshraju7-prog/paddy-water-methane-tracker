# Paddy Water & Methane Tracker

**Satellite radar → water timeline → methane estimate → what a farmer would save with AWD.**

A deployed, mobile-first web tool for rice fields in a couple of mandals of the East
Godavari region, Andhra Pradesh. Pick a field on a map, see its water story for the
season, its estimated methane emissions, and an "if you had drained twice mid-season"
comparison. Telugu and English.

> **Status:** v1 in build. This is a student project. Nobody gets paid for carbon from
> it, the numbers are not decision-grade, and it is not agronomic advice. See
> [Limits & ethics](#limits--ethics).

---

## The idea in one paragraph

Flooded rice paddies go anaerobic and emit methane — about 8% of global human methane.
Sentinel-1 radar sees through monsoon cloud, and open water bounces radar *away* from
the satellite, so a flooded field shows up dark. Track that darkness field by field
across the season and you get an objective water log. Feed the log into the IPCC 2019
Tier 2 rice methane equation and you get tonnes CO₂e. Swap one scaling factor and you
get the Alternate Wetting and Drying (AWD) counterfactual — methane avoided, water
saved, pumping cost saved.

Full explanation: **[`docs/00-project-explainer.md`](docs/00-project-explainer.md)** ← read this first.

---

## Architecture

Two separate pieces, deliberately. STAC queries take minutes; an HTTP request has to
answer in under a second. So nothing is computed at request time.

```
BATCH  (src/, runs on the laptop)            SERVING  (backend/ + frontend/, always on)
─────────────────────────────────            ────────────────────────────────────────
field polygons                                React SPA (mobile-first, te/en)
   ├─ Sentinel-1 GRD   ──┐                          ▲
   ├─ Sentinel-2 L2A   ──┤                          │ JSON, <50 ms
   ├─ NASA POWER       ──┼─► flood classify         │
   └─ SoilGrids        ──┘   season metrics      FastAPI  (no computation, pure reads)
                             IPCC Tier 2               ▲
                             AWD scenario              │
                                   └────────►  POSTGRES ┘
```

| Layer | Tech |
|---|---|
| Pipeline | Python 3.11, GeoPandas, Rasterio, `pystac-client` + `planetary-computer`, `odc-stac` |
| Store | Postgres (no PostGIS — geometry stored as GeoJSON text, all spatial work is offline) |
| API | FastAPI + SQLAlchemy |
| Front end | Vite + React + TypeScript, no map tiles heavier than necessary |
| Deploy | Docker → Azure Container Registry → Azure Container Apps |

---

## Project structure

```
Varaha-Project/
│
├── data/
│   ├── raw/           ← every download, cached forever, never re-fetched
│   │   ├── sentinel1/  sentinel2/  power/  soilgrids/
│   ├── interim/       ← backscatter time series, flood classifications
│   ├── processed/     ← final per-field season results (what gets loaded to Postgres)
│   └── fields/        ← field boundary GeoJSON (anonymised, jittered in public repo)
│
├── notebooks/         ← exploration, day 1–2 geospatial practice
│
├── src/               ← THE PIPELINE (batch)
│   ├── config.py      ← all paths, CRS, thresholds, model constants in one place
│   ├── data/          ← one module per source: fetch + cache
│   ├── features/      ← backscatter → flooded/dry → season metrics
│   ├── models/        ← IPCC Tier 2 methane, AWD scenario, water & cost
│   └── visualization/ ← per-field timeline charts
│
├── backend/           ← THE API (FastAPI + Postgres)
├── frontend/          ← THE APP (Vite + React, Telugu/English)
│
├── models/            ← saved classifiers (v2, once farmer labels exist)
├── reports/figures/   ← generated charts
├── references/        ← IPCC chapter, papers, field notes
├── docs/              ← explainer, 14-day plan, field visit kit, model reference
│
├── environment.yml    ← conda env `varaha`
├── requirements.txt
└── README.md
```

---

## Setup

```bash
# 1. Environment
conda env create -f environment.yml
conda activate varaha

# 2. Config
cp .env.example .env        # edit if needed; no API keys required for v1 data sources

# 3. Sanity check — should print your CRS and paths
python -m src.config

# 4. Open
code varaha-project.code-workspace
```

Every v1 data source is free and keyless: Sentinel-1/2 via Microsoft Planetary Computer,
NASA POWER, SoilGrids.

## Running the pipeline

```bash
# fetch everything for the fields in data/fields/ over the season window
python -m src.data.make_dataset --season kharif-2025

# backscatter time series → flooded/dry → season metrics
python -m src.features.build_features

# IPCC Tier 2 methane + AWD scenario + water/cost
python -m src.models.run_models

# per-field timeline charts into reports/figures/
python -m src.visualization.plot_timeline --all

# load data/processed/season_results.parquet into Postgres
python -m backend.app.load_results
```

## Running the app

```bash
./dev.sh          # FastAPI on :8000, Vite on :5173
```

---

## The 14 days

See [`docs/01-fourteen-day-plan.md`](docs/01-fourteen-day-plan.md) for the day-by-day
version with checkboxes and ship criteria.

| Days | Work | Ship |
|---|---|---|
| 1–2 | Geospatial foundations — CRS, vector/raster, GeoPandas, Rasterio | Load a boundary, clip a raster, save a GeoTIFF |
| 3 | **Field visit 1** — 6–8 farmers, cropping calendar, water practice, boundaries | Transcripts + polygons, same evening |
| 4–5 | Data layer — one module per source, everything cached | One command fills `data/raw/` |
| 6–7 | **Flood detection** — VV time series → flooded/dry → season metrics | Per-field chart with flooded periods shaded |
| 8 | **Field visit 2** — validate satellite dates against farmer recall | An honest agreement rate |
| 9 | Models — IPCC Tier 2 methane, AWD scenario, water & pumping cost | Numbers per field |
| 10–11 | Backend — FastAPI + Postgres, three endpoints | `<100 ms` responses |
| 12 | Front end — mobile map, field card, te/en toggle | Works on a cheap Android |
| 13 | **Deploy** + show one real farmer | A URL, and a page of his confusions |
| 14 | Write-up + rehearse | README, validation note, roadmap |

**Day 7 is the hinge.** If flood detection isn't working by then, stop adding scope.

**Cut list, in order:** scenario comparison → Telugu toggle → the map (a dropdown works)
→ RothC soil carbon. **Never cut the field visits or the deployment.**

---

## Limits & ethics

Written into the UI, not just here.

- **Nobody gets paid for carbon from this.** It is a student project. Said on screen.
- **Not decision-grade.** A 12-day satellite revisit can miss a short drying event
  entirely.
- **Cost savings are a range**, with the pumping-hour and tariff assumptions shown.
- **This does not advise anyone to drain a field.** AWD done wrong loses yield.
- **Anonymised.** Farmer 1, Farmer 2. No names, no survey numbers, jittered coordinates
  in the public repo.

Overclaiming is what got 37 rice carbon projects invalidated. Being visibly careful is
part of the work.

---

## Roadmap

| | |
|---|---|
| **v1** | This. 25–40 fields, threshold classifier, deployed, farmer-validated. |
| **v2** | Trained classifier using farmer-validated labels; a few hundred fields; multi-season. |
| **v3** | Farmer-facing loop — confirm or correct what the satellite saw, in the app. The growing ground-truth dataset is the asset nobody can copy. |
| **v4** | Soil carbon (RothC) — covers VM0042 alongside VM0051. |
| **v5** | Aggregation — project-level totals with uncertainty, in the shape a registry expects. |
