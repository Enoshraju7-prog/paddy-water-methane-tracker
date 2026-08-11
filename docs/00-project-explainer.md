# The project, explained properly

Read this once, slowly. Everything else in the repo assumes you understand this page.

---

## 1. The one-sentence version

> Satellite radar can tell whether a rice field is under water on a given day. Methane
> from a rice field depends almost entirely on how many days it was under water. So
> radar → water timeline → methane estimate → "here's what you'd save if you drained
> twice mid-season."

That chain has four links. Each link is a module in this repo. If you can explain each
link and where it's weak, you can explain the whole project.

---

## 2. Why methane from rice at all

Flooded rice paddies are one of the largest human sources of methane — roughly 8% of
global anthropogenic methane. The mechanism is simple chemistry:

- Standing water seals the soil off from the air.
- Soil goes **anaerobic** (no oxygen).
- Anaerobic microbes (methanogens) break down organic matter and produce **CH₄**
  instead of CO₂.
- The methane bubbles up, or travels out through the rice plant's own aerenchyma
  (its internal air channels — the plant is literally a chimney).

Drain the field for a few days mid-season and oxygen gets back into the soil. The
methanogens stop; methane-eating bacteria (methanotrophs) start. This is **AWD —
Alternate Wetting and Drying**. Done properly it cuts methane roughly 30–50%, saves
about 30% of irrigation water, and doesn't cost yield.

**Methane's leverage:** it's ~27× more warming than CO₂ over 100 years, but its
atmospheric lifetime is only ~12 years. Cutting methane changes the temperature curve
this decade, not in 2100. That's why every carbon registry cares about rice.

**Why this is a Varaha project:** Varaha does soil carbon (VM0042) and rice methane
(VM0051) projects across Indian smallholdings. The hard part of their business isn't
the science — it's *evidence at scale from thousands of tiny fragmented fields*. Which
is exactly what a satellite pipeline is for.

---

## 3. Why radar and not normal satellite images

Your season is the **kharif monsoon** (roughly June–November in East Godavari). Optical
satellites (Sentinel-2, Landsat) see clouds, and during monsoon that's most days. You
would get maybe 3 usable images across the whole season. Useless.

**Sentinel-1** is a Synthetic Aperture Radar (SAR) satellite. It sends its own
microwave pulse down and measures what bounces back. Microwaves pass straight through
cloud. It works at night. Revisit is ~12 days in this region.

The physics that makes flood detection work:

| Surface | What the radar sees | Return signal |
|---|---|---|
| Open water | Smooth — acts like a mirror, bounces the pulse *away* from the satellite | **Very dark** (low σ⁰, ~ −18 dB) |
| Bare/dry soil | Rough — scatters in all directions, some back | Medium (~ −10 dB) |
| Dense vegetation | Volume scattering off leaves and stems | Bright (~ −7 dB) |

So: **flooded field = dark pixel.** You take the average VV backscatter inside a field
polygon on each date, and if it drops below a threshold, you call it flooded.

**The three honest weaknesses** — say these out loud in the interview before anyone
asks:

1. **Revisit gap.** 12 days between looks. A 5-day drying event can be completely
   invisible. Your timeline is an interpolation, not a measurement.
2. **Canopy closure.** Once the rice is tall and dense (~60 days after transplant), the
   canopy hides the water underneath. Backscatter goes *up* even though the field is
   still flooded. A fixed threshold starts failing mid-season — this is the single
   biggest technical risk in the project.
3. **Wind.** Wind roughens the water surface and raises backscatter. A windy acquisition
   day can make a flooded field look dry.

Mitigations for v1: use the VH/VV ratio as a secondary signal, allow a
growth-stage-dependent threshold, and — most importantly — **validate against farmers**
and report the disagreement rate honestly.

---

## 4. Why the architecture is split in two

This is the engineering judgement the plan tells you to say out loud, and it's correct.

Fetching Sentinel-1 scenes from a STAC catalogue, reading the COG windows, and building
a time series takes **minutes per field**. An HTTP request has to answer in under a
second. Those two facts are irreconcilable, so you don't try:

```
  ┌──────────────────────── BATCH (offline, runs weekly / once a season) ─────────┐
  │  field polygons ──► STAC search (Planetary Computer)                          │
  │                     ├─ Sentinel-1 GRD  ──► zonal mean VV/VH per field per date│
  │                     ├─ Sentinel-2 L2A  ──► NDVI on clear days → crop stage    │
  │                     ├─ NASA POWER      ──► rain, temp                         │
  │                     └─ SoilGrids       ──► SOC, clay, pH                      │
  │                              │                                                │
  │                     flood classifier (threshold → flooded/dry per date)       │
  │                              │                                                │
  │                     season metrics (days flooded, drying events, pre-season)  │
  │                              │                                                │
  │                     IPCC Tier 2 methane model ──► baseline + AWD scenario     │
  │                              │                                                │
  │                              ▼  writes rows                                   │
  └──────────────────────────  POSTGRES  ─────────────────────────────────────────┘
                                 ▲
  ┌──────────────────────── SERVING (always on, tiny) ───────────────────────────┐
  │  React SPA (mobile-first, te/en)  ◄──►  FastAPI  ──► one SELECT, <50 ms       │
  └───────────────────────────────────────────────────────────────────────────────┘
```

Consequences worth understanding:

- The API does **no computation**. It is a read-only view over precomputed rows. That's
  why hosting costs are near zero and why the phone experience is fast.
- The pipeline can be slow, ugly, and rerun as often as you like. Different quality bar.
- Everything the pipeline downloads is **cached to disk**, keyed by field + date +
  product. You will rerun the pipeline forty times while debugging. Never re-download.
- **No PostGIS.** All spatial computation happens offline in GeoPandas. The database
  only stores geometry as GeoJSON text for the map to draw. This is a deliberate
  simplification — it keeps the Azure deployment to a plain Postgres.

---

## 5. The methane model — what the numbers actually are

IPCC 2019 Refinement, Volume 4, Chapter 5. **Tier 2** means "use the IPCC equation
structure with region/practice-specific scaling factors" — as opposed to Tier 1
(pure defaults) or Tier 3 (a process model like DNDC).

The equation:

```
CH₄ (kg)  =  EF_i  ×  t  ×  A  ×  10⁻⁶ ... (per field, in tonnes with the 10⁻³)

EF_i      =  EF_c  ×  SF_w  ×  SF_p  ×  SF_o
```

| Term | Meaning | Where you get it |
|---|---|---|
| `EF_c` | Baseline emission factor, continuously flooded, no organic amendment | IPCC default **1.19 kg CH₄ ha⁻¹ day⁻¹** |
| `t` | Cultivation period, days | Farmer interview (transplant → harvest) |
| `A` | Harvested area, ha | Your polygon, area computed in **EPSG:32644** |
| `SF_w` | Water regime **during** the season | **← Sentinel-1.** This is the satellite's contribution |
| `SF_p` | Water regime **before** the season (180 d prior) | **← Sentinel-1.** Also the satellite |
| `SF_o` | Organic amendments (straw, manure, compost) | **← Farmer interview.** Satellite can't see this |

Note what that table tells you: **the satellite supplies two of the four factors and the
farmer supplies the other two.** That is the honest reason the field visits are not
optional — without them you have no `t` and no `SF_o`, and `SF_o` can nearly double the
answer (straw incorporated right before flooding is the single biggest lever in the
whole equation).

The scaling factor values are in [`docs/03-methane-model.md`](03-methane-model.md) and
coded in `pipeline/src/varaha/models/ipcc.py` with the citation next to each constant.

**Converting to CO₂e:** × GWP₁₀₀ for methane. AR6 gives **27** for biogenic methane
(29.8 for fossil). Registries vary — some still use AR5's 28. Make it a config value,
state which one you used, and don't hide it.

**The AWD scenario** is the same equation with `SF_w` swapped from "continuously
flooded" (1.00) to "intermittently flooded, multiple aeration" (0.55). The difference is
your "methane avoided". Then water: ~30% of irrigation volume, converted to pumping
hours, converted to rupees — **given as a range, with the assumptions printed on screen.**

---

## 6. What the farmer actually gets (and what he doesn't)

The plan is blunt about this and it's the most important design instinct in it: a farmer
standing in his field already knows if it's flooded. Telling him that is worthless.

What he cannot get himself:

1. **A season-long objective record.** 120 days of water status, as a log. He can't
   reconstruct that from memory, and it's exactly the evidence a carbon project needs.
2. **Money.** Water saved → pumping hours saved → diesel/electricity saved. This is the
   argument that moves people.
3. **Comparison.** Which fields in the village *already* dry out naturally? Those
   farmers are accidentally doing something close to AWD.

The methane number is mostly for Varaha, not for him. Be honest about that ordering.

**Hard limits you must not cross** (these are in the UI copy, not just the README):

- Nobody is getting paid for carbon from this. It's a student project. Say it on screen.
- The numbers are not decision-grade — a 12-day revisit can miss a drying event.
- Cost savings are a **range** with visible assumptions.
- **Never advise anyone to drain their field.** AWD done wrong loses yield. You are
  showing information, not agronomic advice.
- Anonymise: Farmer 1, Farmer 2. No names, no survey numbers, jittered locations in the
  public repo.

Overclaiming is what got 37 rice carbon projects invalidated. Visible caution is itself
a signal to a science team.

---

## 7. The part that can't be faked

Two field visits.

**Visit 1 (Day 3)** — 6–8 farmers. Cropping calendar, water practice, straw handling,
whether they even control their own irrigation (often they don't — canal schedules do).
Capture boundaries. Transcribe the same evening while you still remember the gestures.

**Visit 2 (Day 8)** — go back holding your satellite-derived dates and ask: *"did this
field dry out around this date?"* Record agreement **and disagreement**. The
disagreements are the valuable data. An honest 71% beats a flattering 95%.

Everything else in this project is reproducible by anyone with the plan. This isn't.

---

## 8. How to know if it's going well

| Checkpoint | Pass condition |
|---|---|
| Day 2 | You can load a polygon, clip a raster to it, and save a GeoTIFF |
| Day 5 | One command fills `data/raw/` and re-running it downloads nothing |
| **Day 7** | **A per-field chart with flooded periods shaded. If not: stop adding scope and fix this.** |
| Day 8 | An agreement rate against farmer recall, written down, whatever it is |
| Day 11 | `GET /api/fields/{id}/timeline` returns in <100 ms from Postgres |
| Day 13 | A URL that loads on a cheap Android phone over 4G, and one farmer has used it |

**Cut list, in this order:** scenario comparison → Telugu toggle → the map (a dropdown
of field names is fine) → RothC soil carbon (a stretch, not core).
**Never cut the field visits or the deployment.**
