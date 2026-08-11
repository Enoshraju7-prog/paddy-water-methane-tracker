# Methane model reference — IPCC 2019 Refinement, Tier 2

Source: *2019 Refinement to the 2006 IPCC Guidelines for National Greenhouse Gas
Inventories*, Volume 4 (AFOLU), Chapter 5.5 — Methane emissions from rice cultivation.

Every constant below is mirrored in `pipeline/src/varaha/models/ipcc.py`. If you change
a number in one place, change it in both, and note why in this file.

---

## Equations

```
CH₄_field (kg)   =  EF_i × t × A
EF_i             =  EF_c × SF_w × SF_p × SF_o        [kg CH₄ ha⁻¹ day⁻¹]
SF_o             =  (1 + Σ_i ROA_i × CFOA_i) ^ 0.59
CO₂e (t)         =  CH₄_field / 1000 × GWP₁₀₀
```

- `t` = cultivation period in days (transplanting → harvest)
- `A` = harvested area, hectares, computed in **EPSG:32644 (UTM 44N)** — never in degrees
- `ROA_i` = rate of organic amendment *i*, t dry-weight ha⁻¹
- `CFOA_i` = conversion factor for that amendment type

---

## EF_c — baseline emission factor

| Value | Scope | Notes |
|---|---|---|
| **1.19** kg CH₄ ha⁻¹ d⁻¹ | Global default (IPCC 2019 Table 5.11) | Uncertainty range 0.80 – 1.76 |

Continuously flooded, no organic amendment. A regional India-specific EF_c would make
this a stronger Tier 2 — flag as a v2 improvement rather than inventing a number.

---

## SF_w — water regime **during** cultivation  ← from Sentinel-1

IPCC 2019 Table 5.12.

| Regime | SF_w | How the pipeline decides |
|---|---|---|
| Continuously flooded | **1.00** | 0 drying events detected |
| Intermittently flooded — single aeration | **0.71** | exactly 1 drying event ≥ 1 obs |
| Intermittently flooded — multiple aeration | **0.55** | ≥ 2 drying events |
| Regular rainfed | 0.54 | not auto-assigned in v1 |
| Drought prone | 0.16 | not auto-assigned in v1 |
| Deep water | 0.06 | not auto-assigned in v1 |

A "drying event" in v1 = a run of ≥1 consecutive Sentinel-1 observations classified dry,
between two flooded observations, inside the cultivation window. **This definition is a
choice, not a fact** — write it in the validation note, because a 12-day revisit means
your drying-event count is a lower bound.

---

## SF_p — water regime **before** cultivation (180 d prior)  ← from Sentinel-1

IPCC 2019 Table 5.13.

| Pre-season regime | SF_p |
|---|---|
| Non-flooded pre-season < 180 days | **1.00** |
| Non-flooded pre-season > 180 days | 0.89 |
| **Flooded pre-season > 30 days** | **2.41** |
| Non-flooded pre-season > 365 days | 0.59 |

Note the size of 2.41. Pre-season flooding more than doubles the estimate — which is why
it's worth pulling radar for the 180 days *before* the season, not just during it. Cheap
to add, large effect.

---

## SF_o — organic amendments  ← from farmer interviews

IPCC 2019 Table 5.14. Conversion factors `CFOA_i`:

| Amendment | CFOA |
|---|---|
| Straw incorporated **shortly** (< 30 d) before cultivation | **1.00** |
| Straw incorporated **long** (> 30 d) before cultivation | 0.19 |
| Compost | 0.17 |
| Farmyard manure | 0.21 |
| Green manure | 0.45 |

Straw timing is the biggest single lever a farmer controls, and the satellite cannot see
it. Ask about it explicitly in both field visits — it's question 6 in
[`02-field-visit-kit.md`](02-field-visit-kit.md).

---

## GWP — methane to CO₂e

| Basis | Value | Use |
|---|---|---|
| **AR6, non-fossil CH₄** | **27** | **Project default** |
| AR6, fossil CH₄ | 29.8 | not applicable to rice |
| AR5 | 28 | some registries still require it |
| AR4 | 25 | legacy |

Configurable via `GWP_CH4` in `pipeline/.env`. Whatever you use, print it on the season
card. Silently switching GWP basis is a classic way to inflate a number by 10%.

---

## AWD scenario

Same equation, one substitution:

```
baseline : SF_w = observed  (usually 1.00 for continuously flooded)
AWD      : SF_w = 0.55      (intermittently flooded, multiple aeration)
avoided  = baseline_CO₂e − awd_CO₂e
```

If a field's observed regime is *already* intermittent, the avoided figure is small or
zero — and that's a genuinely interesting result to show the farmer: *"you're already
doing most of this."*

---

## Water and money

Deliberately crude, deliberately a range, assumptions shown on screen.

```
water_saved_m3   = seasonal_irrigation_m3 × AWD_SAVING_FRACTION      (0.25 – 0.35)
pump_hours_saved = water_saved_m3 / PUMP_DISCHARGE_M3_PER_HOUR
cost_saved       = pump_hours_saved × COST_PER_PUMP_HOUR
```

Defaults live in `pipeline/src/varaha/models/water.py`. Every one of them should be
replaced with a number you got from an actual farmer in Visit 1 — pump HP, hours per
irrigation, diesel price or whether the connection is free-electricity (in AP, farm
power is largely subsidised, which **weakens the money argument** — if that's what you
find, report it; that finding is more interesting than a fake savings number).

---

## Uncertainty — what to say

Do not present a single number without this framing:

- EF_c alone carries roughly ±40% (0.80–1.76 against a 1.19 central value).
- SF_w depends on a drying-event count that a 12-day revisit systematically undercounts.
- SF_o comes from recall, not measurement.

So the field-level estimate is order-of-magnitude honest and rank-order useful — good
for "field A emits more than field B" and "AWD would cut this by roughly half", not good
for issuing credits. Say exactly that.
