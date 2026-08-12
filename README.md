# Paddy Water & Methane Tracker

**Using free satellite radar to work out when rice fields are flooded, and what that
costs the climate.**

East Godavari delta, Andhra Pradesh, India.

> **Status: in build, week 2.** Nothing here is decision-grade. Every day's findings —
> including the days the method failed — go in the [field log](#field-log) below, newest
> first. Current score against reality: **8 out of 12**.

---

## For a reader who is not technical

**The problem.** Rice is grown in flooded fields. Under water, the soil runs out of
oxygen, and the bacteria that take over release **methane** — a greenhouse gas about 27
times stronger than CO₂ over a century. Rice paddies are roughly **8% of all
human-caused methane**.

**The fix already exists.** If a farmer lets the field dry out once or twice mid-season
instead of keeping it flooded throughout — a practice called **Alternate Wetting and
Drying**, or AWD — methane drops sharply. Yield usually holds. Less pumping, so the
farmer's electricity bill drops too.

**So why isn't everyone doing it?** Partly because **nobody can prove it happened.**
Carbon credit programmes need evidence that a field was actually dried. Sending someone
to walk 10,000 fields is impossible. Asking farmers to remember last July is unreliable.
Without proof, there is no payment, and without payment there is much less reason to
change.

**What this project tries to do.** Watch the fields from space instead.

```
   satellite radar  →  when was this field under water?
                    →  how much methane did that produce?
                    →  what would drying it twice have saved?
```

**Why radar and not a normal camera.** This is monsoon country. An ordinary satellite
photo would show clouds for most of the growing season. **Radar makes its own signal and
goes straight through cloud**, day or night. The satellite is Sentinel-1, run by the
European Space Agency. The data is free and public.

**How radar sees water.** Radar sends a pulse down and listens for the echo. Still water
acts like a mirror — the pulse skids off sideways and never comes back. So **flooded
ground shows up dark**. Dry, rough ground scatters the pulse in all directions, some of
it back up to the satellite, so it shows up bright.

That is the whole idea. Watch a field go dark and bright across the season, and you have
its water diary without anyone standing in it.

**It is more complicated than that**, and this repository is partly a record of finding
out how. Keep reading.

---

## Field log

Newest first. Every entry is written on the day, before we know how it turns out, so the
record shows what was claimed and when.

---

### 12 August 2026 — the method failed properly, and that was the useful part

The satellite passed overhead at **05:52 in the morning**. We were standing in the fields
at **06:07** — fifteen minutes later — and walked for an hour and a quarter, taking 52
photographs. Every photograph carries a GPS tag, so we know where each one was taken to
within a few metres. (On the previous trip the camera's GPS was off and locations had to
be reconstructed from map links afterwards. Those were guesses. These are measurements.)

The 52 photos group into **12 locations**. Every single one held **5 to 7 centimetres of
standing water**, clearly visible. The farmers, asked directly, said water is present for
the *entire* growing season — they never drain it.

So the correct answer is **12 out of 12 flooded**, and there is no room to argue about it.

#### The scoreboard

| Rule | Score |
|---|---|
| The original rule: is the field darker than a fixed line? | **0 / 12** |
| Ask the second radar channel (VH) the same question | **8 / 12** |
| Ask how far VH has fallen from that field's own dry level | **8 / 12** |

Not "needs tuning". **Zero.** And the clever third rule — the one that looked promising on
11 August — turned out to be **no better than the simple one**. We tested 17 different
settings for it. None beat 8 out of 12.

#### Why the first rule failed

The textbook is right that **open water** is dark. But a rice field is not open water. It
is thousands of **stems standing up out of the water**.

Picture the corner where a wall meets the floor. Throw a ball into that corner and it
comes straight back at you. A rice stem meeting the water surface makes exactly that
shape. So the radar pulse hits the water, bounces sideways into a stem, and is sent
**straight back up to the satellite**. This is called **double bounce**.

The result is the opposite of what the rule assumed:

- a **bare, just-flooded** field, before the plants grow — genuinely dark ✅
- a **flooded field full of growing rice** — **bright** ❌

The rule was never measuring "is there water". It was measuring "is this field in the
fortnight right after planting, before the plants come up". For the other four months of
the season it was blind.

#### The question this leaves

The **same four locations fail under every rule we have tried**. They are all in the
southern half of the walk — and looking back through a year of satellite data, they are
the same four whose readings never showed the dip that the others did when they were
planted.

So the next question is not *"what number should the threshold be?"*. It is **"what is
different about those four fields?"**

#### Four other things settled the same day

**There is no winter rice crop here.** We pulled 20 months of satellite data, back to
December 2024, looking for a second flooding each winter. There isn't one. This matters
more than it sounds: the international methane formula has a multiplier for whether the
field was flooded in the months *before* the season, and it is either 1.0 or 2.41.
Getting it wrong would have **more than doubled every number this project produces**.
It's 1.0.

**The season starts a month later than assumed** — the settings said 15 June; the
satellite curves and the farmers both say mid-July.

**The crop is longer than assumed** — the model was using 120 days. Planting was late
June and harvest is late November or mid-December: **150 to 173 days**. Methane scales
directly with this, so that was 25–44% being left out.

**We found a faster source of satellite data.** We had been using Microsoft's copy of the
archive. The European Space Agency publishes to its own system within hours, while
Microsoft's copy lagged more than a day. For a project built on *same-day* checking, that
difference is the whole point. Both are now wired up.

#### And two more bugs

One made the program crash the second time you ran it. The other made it fail *silently*
— it would finish, report success, and produce nothing at all. Three of the twelve
locations disappeared that way before anyone noticed.

---

### 11 August 2026 — the first real result

On 11 August 2026 we walked into the paddy block near Sarpavaram and photographed three
fields. All three clearly held **transplanted rice standing in water**.

Then we asked the satellite what it thought.

![First ground check](docs/img/05-first-ground-check.png)

**The satellite said all three were dry.** Zero out of three.

#### Why it failed

The "water is a mirror" rule is true — for **bare** water. But these fields had rice
stems sticking up out of the water. The radar pulse hits the water, bounces sideways
into a stem, and comes **straight back up** to the satellite. The field reads *brighter*,
not darker. This is called **double-bounce**, and it means a fixed brightness threshold
only works during the short window between flooding a field and the seedlings growing
tall enough to matter.

#### What looks more promising

Instead of asking *"is this field darker than a fixed line?"*, ask *"**how much darker
has this field become compared to its own dry season?**"* Every field then gets judged
against itself, which removes the differences between fields that a single global
threshold cannot handle.

Measured against a two-pass pre-season baseline:

| Field | Observed | VV drop | **VH drop** |
|---|---|---|---|
| F001 | flooded | 1.3 dB | **5.1 dB** |
| F002 | flooded | 3.0 dB | **6.0 dB** |
| F003 | flooded | 3.9 dB | **5.0 dB** |
| F004 | not visited | 8.0 dB | **8.4 dB** |
| F900 | **not** paddy | 1.1 dB | **3.3 dB** |

The second radar channel (**VH**) separates flooded fields from the non-paddy control;
the first (VV) does not. But the gap between the weakest real field (5.0 dB) and the
control (3.3 dB) is only **1.7 dB**, on a sample of four fields with one control.

**That is suggestive, not proven.** It is written down here so that if it falls apart on
a bigger sample, the record shows what was claimed and when.

> **Follow-up, 12 August:** it partly did. On four times the sample, judging each field
> against its own dry season scored **exactly the same** as the far simpler rule of just
> reading the VH channel — 8 out of 12 either way. The idea was not wrong, but it added
> nothing. Left standing here, unedited, because that is the point of writing it down.

Raw numbers: [`data/validation/2026-08-11-first-ground-check.csv`](data/validation/2026-08-11-first-ground-check.csv).
Chart code: [`src/visualization/plot_validation.py`](src/visualization/plot_validation.py).

---

## What has actually been built so far

| | Status |
|---|---|
| Study area fixed to the real villages | done |
| Satellite pass calendar, derived not assumed | done — every 12 days, 05:52 IST, orbit 19 |
| Download + cache layer (fetch once, never re-fetch) | done |
| Sentinel-1 backscatter per field, per pass | done |
| Same-day satellite feed, hours after the pass | done — 12 Aug 2026 |
| Ground-truth trips | done — 11 Aug (3 fields), 12 Aug (12 GPS-tagged locations) |
| 20 months of history, Dec 2024 → Jul 2026 | done — 48 passes |
| Validation of satellite vs reality | done — **and it is scored honestly: 8/12** |
| Pre-season flooding multiplier settled (1.0, not 2.41) | done — the biggest single risk in the model |
| Flood classification that survives contact with reality | **in progress — this is the gate** |
| Methane model (IPCC 2019 Tier 2) | not started |
| AWD comparison | not started |
| Web app | not started |

Nothing below the gate gets built until a satellite can reliably tell whether a field has
water in it. Everything after that link in the chain depends on it being right.

### Five bugs found along the way

Each one produced believable but wrong numbers, silently. They are worth listing because
"the code ran without an error" is not the same as "the answer is right".

1. **Mosaic ordering.** One satellite pass arrives as several overlapping strips. Loaded
   in the order the catalogue happened to return them, the later strip's empty pixels
   painted over the earlier strip's real data — **93% of the study area was blanked, with
   no error raised.** Fixed by sorting on acquisition time, plus an assertion that fails
   loudly if it ever comes back.

2. **Averaging decibels.** Radar brightness is measured on a logarithmic scale.
   Averaging those numbers directly is arithmetically wrong. Two pixels at −20 dB and
   −5 dB average to −12.5 dB the wrong way and −7.9 dB the right way. That 4.6 dB gap
   straddles the flood threshold.

3. **Guessing the revisit interval from the shortest gap.** A satellite handover on
   25 June 2026 produced a one-off 7-day gap. Taking the minimum would have projected a
   7-day calendar and wasted real field trips. The correct answer is the **mode**: 12 days.

4. **A crash that only happened the second time you ran it.** The first run downloaded
   the data and worked. The second run read it back from the cache — down a code path
   that skipped an import the first path had quietly relied on — and died.

5. **Total failure, reported as success.** Worse than the above, because there was
   nothing to notice. Each field was processed inside a "carry on if this one fails"
   block, and the message only printed in verbose mode. So the program hit bug 4 on every
   single field, swallowed all twelve errors, exited cleanly, and produced an empty
   result. Three locations were missing from a chart before anyone spotted it. *"The code
   ran without an error"* is not the same as *"the answer is right"*.

---

## What happens next

| When | What |
|---|---|
| **Next** | Work out what is different about the four locations that fail every rule |
| **24 Aug** | Third ground check, on the morning of the next satellite pass |
| Then | Ask the farmers the questions 12 Aug raised: straw handling, pre-harvest drying, canal vs pump control |
| Then | Correct the season dates and crop length in the model, now that the real ones are known |
| Then | Draw 10–15 field boundaries and run the whole season through |
| Then | IPCC Tier 2 methane per field, as a range not a single number |
| Then | AWD comparison — methane avoided, water saved, pumping cost saved |
| Then | Mobile web app, Telugu and English |

---

## Honesty rules this project runs on

- **Report what was measured.** The score today is 8 out of 12, written down and dated.
  It would have been easy to move the threshold until the chart looked good — and the
  number would then have been *tuned to agree* rather than *measured to be true*. An
  honest 67% you can improve on beats a flattering 95% you cannot trust. The rows where
  satellite and ground disagree are the most valuable rows in the table.
- **Flag, don't fudge.** When the radar becomes unreliable, mark the reading
  low-confidence. Never quietly shift a threshold to make a curve look right.
- **Every number carries its uncertainty.** The methane emission factor has a published
  range, so the methane figure is a band, not a point.
- **Drying events are a lower bound.** A 12-day revisit cannot see a drying event
  shorter than 12 days. This biases the estimate *upward*, which is the safe direction.
- **Nobody gets paid for carbon from this.** It is a portfolio project. It is not
  agronomic advice, and it does not tell anyone to drain a field — AWD done wrong costs
  yield.

### Anonymised from the first commit

Farmers appear as `F001`, `Farmer 1`. **No names, no survey numbers, no phone numbers,
ever, in any tracked file.** Real field boundaries, interview notes and photographs live
in `data/fields/`, which is gitignored for privacy rather than for size. Published
coordinates are jittered.

---

## For developers

Cookiecutter Data Science layout. conda, **conda-forge only** — mixing channels is the
quickest route to a `rasterio` that imports and then segfaults.

```bash
conda env create -f environment.yml
conda activate varaha

python -m src.config                      # print resolved config, create dirs
python -m src.data.overpass               # next Sentinel-1 pass dates
python -m src.data.sentinel1_cdse         # today's reading, straight from ESA
python -m src.features.flooding --sweep   # score every flood threshold against reality
python -m src.visualization.plot_validation   # regenerate the chart above
```

```
src/
  config.py            every path, CRS, threshold and constant. no magic numbers elsewhere
  data/                fetchers + cache. nothing here computes features
  features/            flooding classification, season metrics
  models/              IPCC, methane, water/cost
  visualization/       plots
data/
  raw/ interim/ processed/   gitignored, re-fetchable
  fields/                    boundaries + interviews. gitignored for PRIVACY
  validation/                tracked — accuracy claims need visible rows
backend/               FastAPI, read-only
frontend/              Vite + React + TypeScript
```

**The two-CRS rule.** `EPSG:4326` stores and displays; `EPSG:32644` (UTM 44N) measures.
Every area, distance and buffer goes through the projected CRS. Area computed in degrees
is wrong by about 1.2 × 10¹⁰ on a real field here.

Conventions, and the full list of traps that silently produce plausible wrong answers,
are in [`CLAUDE.md`](CLAUDE.md).

### Read these

| File | What it gives you |
|---|---|
| [`explanation.md`](explanation.md) | The whole idea in plain language |
| [`docs/00-project-explainer.md`](docs/00-project-explainer.md) | Long-form walkthrough |
| [`docs/03-methane-model.md`](docs/03-methane-model.md) | Every IPCC constant with its table reference |
| [`docs/02-field-visit-kit.md`](docs/02-field-visit-kit.md) | Consent script, questions, boundary procedure |
| [`docs/handoff-prompt.md`](docs/handoff-prompt.md) | The whole state of the project in one pasteable block |

---

## Data sources

All free and public. Two of them need a free account; none costs anything.

| Source | Used for | Access |
|---|---|---|
| Sentinel-1 (ESA, via Microsoft Planetary Computer) | radar backscatter — the archive of record | anonymous |
| Sentinel-1 (ESA, via Copernicus Data Space) | the **same-day** reading, hours after the pass | free account |
| Sentinel-2 (ESA) | optical NDVI — crop growth, cloud permitting | anonymous |
| IPCC 2019 Refinement, Vol. 4 Ch. 5 | methane emission factors and scaling factors | published document |

Both Sentinel-1 sources are wired up and used together: Copernicus answers *today*,
Microsoft's copy is the record once it catches up. Where they overlap, the archive wins.

---

## Roadmap

| | |
|---|---|
| **v1** | This. 10–15 fields, deployed, validated against photographs. |
| **v2** | Trained classifier using ground-truth labels; a few hundred fields; multi-season. |
| **v3** | Farmer-facing loop — confirm or correct what the satellite saw, in the app. The growing ground-truth dataset is the asset nobody can copy. |
| **v4** | Soil carbon (RothC). |
| **v5** | Project-level aggregation with uncertainty, in the shape a registry expects. |
