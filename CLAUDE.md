# CLAUDE.md

Working notes for anyone — human or agent — writing code in this repo.

## What this is

A mobile-first web tool for rice fields in the East Godavari delta, Andhra Pradesh.
For each field it shows: the water timeline across the season (from Sentinel-1
radar), estimated seasonal methane in tonnes CO₂e (IPCC 2019 Refinement, Tier 2),
and an AWD counterfactual — methane avoided, water saved, pumping cost saved.
Telugu and English.

Two seasons, two jobs:

- **Kharif 2025** is complete. It builds and tests the pipeline.
- **Kharif 2026** is live right now. It supplies *same-day* ground truth.

The one-line version: satellite radar sees when a field is flooded → flooded days
drive the methane number → drying it out is the intervention.

## Read these before writing code

| File | What it gives you |
|---|---|
| [explanation.md](explanation.md) | The whole idea in plain language, including the canopy problem |
| [docs/00-project-explainer.md](docs/00-project-explainer.md) | Long-form walkthrough of the four links |
| [docs/03-methane-model.md](docs/03-methane-model.md) | Every IPCC constant with its table reference |
| [docs/02-field-visit-kit.md](docs/02-field-visit-kit.md) | Consent script, questions, boundary procedure |

The plan is phase-by-phase. **Do not implement ahead of the current phase.**
Building four phases of speculative code is how this repo got reset once already.

## Layout

Cookiecutter Data Science, matching the Fitness Sensor project's conventions.

```
src/
  config.py            every path, CRS, threshold, constant
  data/                fetchers + cache. nothing here computes features
  features/            flooding classification, season metrics
  models/              IPCC, methane, water/cost
  visualization/       plots. the Phase 4 timeline chart is the project gate
data/
  raw/                 satellite downloads. gitignored, re-fetchable
  interim/ processed/  gitignored
  fields/              boundaries + interviews. gitignored for PRIVACY, not size
backend/               FastAPI, read-only
frontend/              Vite + React + TS
docs/ notebooks/ reports/
```

## Environment

conda, **conda-forge only**. Mixing channels is the single most common way to end
up with a rasterio that imports but segfaults.

```bash
conda env create -f environment.yml
conda activate varaha

python -m src.config            # print resolved config, create dirs
python -m src.data.overpass     # next Sentinel-1 pass dates
```

## Rules that are not negotiable

### 1. No AI attribution in git

No `Co-Authored-By: Claude` trailers. No "generated with" lines in commits, PR
bodies, or file headers. This is a portfolio repo tied to a job application.

### 2. Findings go in the README, never in a new dated file

`README.md` carries a **field log**, newest entry first. Every push that produced a
finding adds an entry there — dated, in plain language, readable by someone who has
never touched a satellite. Do **not** create `docs/YYYY-MM-DD-*.md`; a reader who
lands on the repo sees the README and nothing else, so that is where the work has to
be visible.

Old entries are never edited to look better. If a later day contradicts an earlier
claim, the earlier entry stays as written and gets a **follow-up note** under it.
That contradiction is the evidence the project is honest.

### 3. The two-CRS rule

- `EPSG:4326` (WGS84) — **stores** and **displays**. GeoJSON, the web map, the DB.
- `EPSG:32644` (UTM 44N) — **measures**. Every area, distance, buffer.

Area computed in degrees is wrong by ~1.2 × 10¹⁰ on a real field here. Both are in
`src/config.py` as `CRS_WGS84` and `CRS_UTM_44N`. Never hardcode either.

### 4. Farmer data is anonymous from the first commit

`F001`, `Farmer 1`. No names, no survey numbers, no phone numbers, ever, in any
tracked file. Coordinates get jittered before anything is published. Real
boundaries, interviews and photos live under `data/fields/` and `references/`,
both gitignored.

### 5. No magic numbers outside `src/config.py`

If a threshold, constant or date appears in a module, it belongs in config.

### 6. Flag, don't fudge

When the radar becomes unreliable — canopy closure being the main case — mark the
observation **low-confidence**. Do not silently reclassify it or shift the
threshold to make the curve look right. An unfalsifiable correction is exactly
what this project exists to avoid.

## Correctness traps

These are specific, real, and each one silently produces plausible wrong answers.

**Averaging backscatter in dB.** σ⁰ is logarithmic. Convert to linear power,
average, convert back. Averaging dB directly biases every field mean.

**Mixing orbit directions.** Ascending and descending passes see different
geometry, so the backscatter level differs. Mixing them injects steps into the
time series that look exactly like drying events. Pin one — `s1_orbit_direction`.

**Inferring revisit cadence from the minimum gap.** Platform handovers (Sentinel-1A
→ 1D on relative orbit 19, 25 Jun 2026) produce a one-off short gap. `min()` latches
onto it and projects an entirely wrong calendar. Use the **mode**. This already
happened once and would have wasted real field trips.

**Using RTC for the pass calendar.** `sentinel-1-rtc` lags in processing and drops
scenes. Use `sentinel-1-grd` for *dates*; RTC stays correct for *backscatter*.

**Canopy closure, and how little headroom the threshold really has.** Around 60
days after transplant the leaves hide the water, VV rises, and a fixed threshold
reads "dry". See rule 6.

The margin is much tighter than a generic land-cover table suggests. "Dense
canopy ≈ −7 dB" is a *forest/shrub* figure and does not describe rice: a paddy
canopy stands in standing water, which keeps absorbing and reflecting the pulse
away even once the leaves close. The rice SAR literature puts peak-of-season VV
nearer **−16 to −14 dB** — i.e. as little as ~1 dB above the −16 dB threshold,
not the ~9 dB of comfort −7 dB implies.

Consequence: canopy closure may not just add noise, it may push mid-season
observations across the threshold wholesale. Do not assume the budgeted risk;
**measure it** — read the Phase 4 curves, find where each field's series peaks,
and if the peak sits within ~2 dB of the threshold, that field's mid-season
observations are low-confidence by construction (rule 6), regardless of what the
threshold says. Trust your own curves over both numbers above.

**12-day revisit undercounts drying events.** A drying event shorter than the gap
is invisible. Every drying-event count is a **lower bound** — say so wherever the
number appears. The bias over-estimates methane, which is the right direction to
be wrong in.

## Style

- Comments explain *why*, not *what*. A comment restating the code is noise; a
  comment recording why a threshold is −16 dB is the point.
- Module docstrings say what the module is for and how to run it.
- `from __future__ import annotations`, modern type hints, `ruff` clean.
- Typer for CLIs, rich for terminal output.
- Build for one field, print the numbers, sanity-check them, *then* loop.

## Sanity checks

| Thing | Expected |
|---|---|
| Field area | 0.2–2 ha. Wildly off → wrong CRS |
| σ⁰ VV ponded paddy | −22 to −17 dB |
| σ⁰ VV bare / drained soil | ≈ −10 dB |
| σ⁰ VV rice at peak canopy | −16 to −14 dB. **Not −7 dB** — see below |
| Passes per season per field | ~13 at a 12-day revisit |
| Second pipeline run | downloads nothing (cache) |
| API response | well under 100 ms, zero computation |

## Reporting numbers

Every figure gets its uncertainty attached. EF_c has a published range
(0.80–1.76), so the methane number is a band, not a point. Water savings are a
range with the assumptions carried on the result object so the UI can print them.

Report what you actually measure. An honest 71% agreement beats a flattering 95%;
the rows where satellite and observation disagree are the most valuable rows in
the table.
