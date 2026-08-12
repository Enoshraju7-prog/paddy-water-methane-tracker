# Handoff prompt

Paste the block below into any model to bring it up to speed on this project.
Regenerate it whenever the state changes materially (a new score, a new phase).

---

I'm building a portfolio project for a job application at Varaha (a carbon-removal
company working with Indian smallholder farmers). I'm a beginner — explain things
simply and show me the reasoning, don't just hand me code. Here is the full state.

## What the project is

A mobile-first web tool for rice fields in the East Godavari delta, Andhra
Pradesh, India. For each field it should show three things:

1. **The water timeline** across the growing season — when the field was flooded,
   detected from Sentinel-1 satellite radar.
2. **Estimated seasonal methane** in tonnes CO₂e, using the IPCC 2019 Refinement
   (Volume 4, Chapter 5), Tier 2 method.
3. **An AWD counterfactual** — AWD is "alternate wetting and drying", where a
   farmer lets the field dry out periodically instead of keeping it flooded. The
   tool estimates methane avoided, water saved, and pumping cost saved if the
   farmer adopted it.

Telugu and English. Stack: Python (conda/conda-forge) for the pipeline, FastAPI
read-only backend, Vite + React + TypeScript frontend.

## The scientific chain the whole thing rests on

Flooded rice paddy → the mud underwater has no oxygen → anaerobic bacteria
produce **methane** (~27× worse than CO₂ per tonne over 100 years). Fewer flooded
days = less methane. So:

satellite radar sees when a field is flooded → flooded days drive the methane
number → drying the field out is the intervention.

Every link after the first depends on the first one working.

## Where the data comes from

- **Sentinel-1** C-band SAR (radar). Radar, not optical, because this is monsoon
  season — an optical satellite would photograph four months of cloud.
- Descending orbit, **relative orbit 19**, 12-day revisit, overpass ~05:52 IST.
- Two sources, both wired up:
  - **Microsoft Planetary Computer** — `sentinel-1-rtc` for backscatter,
    `sentinel-1-grd` for pass dates. Anonymous access. Lags 1+ days.
  - **Copernicus Data Space Ecosystem (CDSE)** Sentinel Hub Statistical API —
    publishes **same-day**. Needs an OAuth client-credentials pair in `.env`.
    This matters because the validation method is same-day ground truth.

## Two seasons, two different jobs

- **Kharif 2025** is complete. It exists to build and test the pipeline.
- **Kharif 2026** is happening right now. It supplies *same-day* ground truth:
  I walk the fields on the morning of a satellite pass and photograph what is
  actually there, so I can score the satellite against reality with no argument.

## What I have done so far

**Fieldwork.** Two trips. On **12 August 2026** the satellite passed at 05:52 IST
and I was standing in the fields at 06:07 — fifteen minutes later. I walked for
about 75 minutes and took 52 GPS-tagged photographs across a footprint of roughly
1.0 km × 350 m. Those 52 photos group into **12 locations**. Every one of the 12
was holding 5–7 cm of standing water, clearly visible.

**Farmer interviews.** Established, by asking directly:
- Water is present the **entire crop period** — they never drain it deliberately.
- Transplanting was late June / mid-July 2026; harvest is late Nov / mid-Dec.
  So the crop runs **150–173 days**, not the 120 my config assumed.
- After harvest they wait ~20 days and start the next crop.
- Water depth is only 2–3 inches.

**Code written and committed** (repo: `Enoshraju7-prog/paddy-water-methane-tracker`):
- `src/config.py` — every path, CRS, threshold and IPCC constant in one place.
- `src/data/overpass.py` — computes the Sentinel-1 pass calendar.
- `src/data/sentinel1.py` — Planetary Computer fetch + per-field time series.
- `src/data/sentinel1_cdse.py` — same-day fetch from Copernicus.
- `src/data/cache.py` — so a second run downloads nothing.
- `src/features/flooding.py` — the flood classification rule and its scoring.
- `src/visualization/backscatter.py` — small-multiples time series + a diverging
  bar chart of distance-from-threshold.
- `README.md` — carries a dated field log, newest first, in plain language.

**Data pulled:** 48 satellite passes for all 12 locations, December 2024 through
July 2026 (20 months), plus the same-day 12 August 2026 reading.

## The central finding — and the current blocker

My original rule was the textbook one: **open water is a mirror, it reflects the
radar pulse away from the satellite, so flooded ground looks dark**. I set the
line at σ⁰ VV ≤ −16 dB.

Scored against 12 locations that were *definitely* flooded: **0 out of 12.**

**Why it fails: double bounce.** A rice field is not open water — it is thousands
of stems standing *in* water. A stem meeting a water surface forms a corner
reflector (like the corner where a wall meets the floor: throw a ball in and it
comes straight back). The pulse bounces off the water, off the stem, and straight
back to the satellite. So a **flooded field with growing rice is BRIGHT, not
dark**. Only the bare puddled field in the fortnight right after transplanting is
dark. My rule was detecting the puddling window, not the season.

**What I tried next.** Instead of "how dark is it?", ask "how far has it fallen
from its own dry-season level?" — a per-field baseline, which cancels between-field
differences and also cancels the constant calibration offset between σ⁰ and γ⁰.
And use **VH** polarisation instead of VV, because VH drops further when a paddy
floods.

| Rule | Score |
|---|---|
| Original: σ⁰ VV ≤ −16 dB | **0 / 12** |
| Plain VH ≤ −16 dB | **8 / 12** |
| VH dropped from its own baseline (17 thresholds swept) | **8 / 12** |

The clever version was **no better** than the simple one. The baselines landed at
−15 to −16 dB, essentially on top of the threshold, so the per-field reference
added no information.

**The same four locations fail under every rule tried: C01, C02, C03, C05.** They
are the southern half of the walk, and they are the same four whose VV curves
never dipped at any point in the whole season. Diagnosing what is different about
those four is the open question — *not* further threshold tuning.

## Things now settled (don't re-derive these)

- **SF_w = 1.00** (continuously flooded) — confirmed three ways.
- **SF_p = 1.00, not 2.41** — 20 months of radar show no winter flooding, so
  there is no second rice crop before the season. This was the single biggest
  multiplier risk in the whole model; getting it wrong would have more than
  doubled every number the project produces.
- Season start is **mid-July**, not the 15 June currently in config.
- Cultivation is **150–173 days**, not the 120 currently in config.
  (These last two are known-wrong config values I have deliberately flagged
  rather than silently changed.)

## Where I am in the plan

The plan is 14 days. Days 1–5 (foundations, field visit, data plumbing) are done.
**Days 6–7 are flood detection, and that is exactly where I am stuck.** The plan
itself says this is the gate: if flood detection isn't working by Day 7, stop
adding features and fix it.

Still to build, in order, and *not before the gate passes*:
- the IPCC methane model (`src/models/`)
- the AWD counterfactual (water + pumping cost)
- the seasonal timeline chart (the plan calls this the project gate for Phase 4)
- FastAPI backend, React frontend, Telugu/English

## What I'm aiming at

A defensible, honest measurement — the kind of thing that would survive a
technical interview at a carbon company and that I could write up on LinkedIn or
as a short paper. The reference project I'm studying is
**github.com/microsoft/rice-irrigation-mapping-s1s2** (Microsoft AI for Good +
The Nature Conservancy + UC Berkeley + Yale; paper arXiv 2507.08605) — same
country, same crop, same satellite, same AWD-vs-continuously-flooded question,
~1,400 Punjab plots. They reach the same conclusion I reached by measurement:
one backscatter threshold is not enough, so they use handcrafted VV/VH features
plus learned embeddings into Random Forest / LightGBM.

## Rules I work under (please respect these)

1. **No AI attribution anywhere in git** — no `Co-Authored-By`, no "generated
   with" lines. It's a portfolio repo tied to a job application.
2. **Two-CRS rule.** `EPSG:4326` stores and displays. `EPSG:32644` (UTM 44N)
   measures — every area, distance and buffer. Area computed in degrees is wrong
   by ~10¹⁰ here.
3. **Farmer data is anonymous from the first commit.** `F001`, `Farmer 1`. No
   names, no survey numbers, no phone numbers, ever, in any tracked file.
   Coordinates get jittered before publication.
4. **No magic numbers outside `src/config.py`.**
5. **Flag, don't fudge.** When the radar is unreliable, mark the observation
   low-confidence. Never quietly reclassify it or move the threshold to make the
   curve look right.

## Correctness traps I have to keep avoiding

- **Never average backscatter in dB.** σ⁰ is logarithmic — convert to linear
  power, average, convert back. (A *median* in dB is fine, because a median is
  order-based and dB is monotonic in power.)
- **Never mix ascending and descending passes.** Different geometry, different
  backscatter level; mixing them injects steps that look exactly like drying
  events.
- **Never infer revisit cadence from `min()` of the gaps.** A platform handover
  (Sentinel-1A → 1D on relative orbit 19, 25 Jun 2026) creates one short gap that
  `min()` latches onto and projects a wrong calendar from. Use the **mode**.
- **A 12-day revisit undercounts drying events.** Any drying shorter than the gap
  is invisible, so every drying-event count is a **lower bound** and must be
  labelled as one. It biases toward over-estimating methane, which is the right
  direction to be wrong in.
- **Report what I actually measure.** An honest 67% beats a flattering 95%; the
  rows where satellite and ground observation disagree are the most valuable rows
  in the table. Every figure carries its uncertainty — EF_c has a published range
  of 0.80–1.76, so the methane number is a band, not a point.

## What I want from you

[Say here what you want — e.g. "help me work out what is different about C01,
C02, C03 and C05", or "explain what VH polarisation actually is, simply", or
"help me plan what to ask the farmers on the 24 August trip".]
