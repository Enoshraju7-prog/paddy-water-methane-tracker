# Paddy Water & Methane Tracker — the explanation

Read this once, slowly, before planning anything. The goal is that the project
sits in your head as a story you can tell, not a list of tasks.

---

## What this project actually is

You pick a rice field on a map. You see, for the whole season: when it was under
water, roughly how much methane it emitted, and what it would have saved — in
methane, water, and rupees — if the farmer had drained it twice mid-season. On a
phone. In Telugu or English.

That's it. Everything else is detail.

---

## Why rice methane

Flooded paddies are ~8% of all human methane emissions. The mechanism is simple:

Standing water seals the soil from air → soil goes anaerobic → methanogen
microbes break down organic matter and make **CH₄** instead of CO₂ → the gas
escapes, largely up through the rice plant's own internal air channels. The plant
is literally a chimney.

Drain the field for a few days mid-season and oxygen returns. Methanogens stop.
This is **AWD — Alternate Wetting and Drying**. Done right: ~30–50% less methane,
~30% less water, no yield loss.

Methane is ~27× more warming than CO₂ over 100 years but only lives ~12 years in
the atmosphere. Cutting it bends the temperature curve *this decade*. That's why
every carbon registry cares.

**Why Varaha specifically:** they run soil carbon (VM0042) and rice methane
(VM0051) projects across Indian smallholdings. Their hard problem isn't the
science — it's *getting evidence at scale from thousands of tiny fragmented
fields*. That's what a satellite pipeline is for. This project is a small, honest
version of their actual product.

---

## The trick: how a satellite sees water

Your season is the monsoon. Optical satellites see clouds — you'd get maybe 3
usable images in 150 days. Useless.

**Sentinel-1 is radar.** It fires its own microwave pulse down and measures the
echo. Microwaves go through cloud. Works at night. Revisits every ~12 days.

The physics that makes this work:

| Surface | Why | Radar returns |
|---|---|---|
| Open water | Smooth — mirrors the pulse *away* from the satellite | **Very dark** (~ −18 dB) |
| Bare soil | Rough — scatters some back | Medium (~ −10 dB) |
| Dense canopy | Bounces around leaves and stems | Bright (~ −7 dB) |

**So: flooded field = dark pixel.** Average the brightness inside a field polygon
on each date. Below a threshold → flooded. That's the entire core algorithm. It is
not complicated. Making it *trustworthy* is the hard part.

### The torch analogy, if the physics feels abstract

Forget satellites. You're in a dark room with a **torch**, and you can only see
something if the light comes *back* to your eye.

1. **A mirror tilted away from you** — all the light bounces off at an angle,
   away. Nothing returns. You see **black**.
2. **A rough concrete wall** — light hits the bumps and scatters everywhere, and
   some happens to come back. You see **grey**.
3. **A thick bush** — light goes in, rattles off leaf, twig, leaf, and a lot of it
   comes back out toward you. You see **bright**.

The satellite is the torch. Water is the mirror, bare soil is the wall, and a
grown rice crop is the bush.

---

## The canopy problem — the biggest technical risk

**"Canopy" just means the leafy roof the plants make when you look down from
above.** A forest from a plane: you don't see ground, you see a ceiling of
treetops. Rice does the same, just shorter.

**Early season** (~2 weeks after transplanting) — small seedlings, gaps
everywhere, and from above you mostly see water:

```
 🌱   🌱   🌱   🌱      ← thin, gaps everywhere
~~~~~~~~~~~~~~~~~~~     ← the water is visible
```

**Mid–late season** (~60 days in) — the plants have grown into each other and
from above you see only leaves. The water is completely hidden underneath:

```
🌾🌾🌾🌾🌾🌾🌾🌾🌾🌾     ← solid green roof = DENSE CANOPY
░░░░░░░░░░░░░░░░░░░     ← water still there, but invisible
```

So "dense canopy" isn't a special thing. It's just **the crop when it's grown up.**

### Why that breaks the algorithm

```
DAY 15                          DAY 75
     📡                              📡
      ↓  pulse reaches water          ↓  pulse hits leaves
 ~~~~~~~~~~~  →  bounces away    🌾🌾🌾🌾🌾  →  bounces back
   DARK ✅ correct                BRIGHT ❌ wrong
                                 ░░░░░ (water still there!)
```

The field is **still flooded**. Nothing changed underneath. But the radar now
reads bright, and the rule *"bright = not flooded"* gives the wrong answer. The
crop grew a roof over your evidence.

This is not a bug you can code away — it is physics. The water is genuinely
hidden.

### How you deal with it — three options, in order of honesty

1. **Know when it happened.** Use Sentinel-2 (a normal camera satellite) to
   measure how green the field is. When greenness jumps, the canopy has closed.
   Now you know the date after which radar stopped being reliable.
2. **Mark those readings as low-confidence** instead of pretending. Put it in the
   write-up: *"after day 62 the canopy closed and my flood detection degrades."*
   An interviewer will respect that far more than a clean-looking number.
3. **Use VH as well as VV.** The satellite sends two flavours of pulse. VH reacts
   more to vegetation structure and degrades a bit more gracefully under a canopy.
   Helps — doesn't solve.

---

## The chain — four links

```
radar  →  water timeline  →  methane estimate  →  "what if you'd used AWD"
```

If you can explain each link and where it's weak, you can explain the whole
project in an interview.

---

## The math (this is the part worth memorising)

IPCC 2019 Refinement, Tier 2. Tier 2 means "IPCC's equation, your local factors."

```
CH₄  =  EF_c × SF_w × SF_p × SF_o  ×  t  ×  A
```

| Term | What it is | **Who supplies it** |
|---|---|---|
| `EF_c` | Baseline: 1.19 kg CH₄/ha/day | IPCC default |
| `SF_w` | Water regime **during** the season | **← the satellite** |
| `SF_p` | Water regime **before** the season | **← the satellite** |
| `SF_o` | Straw / manure added to the soil | **← the farmer** |
| `t` | Days from transplant to harvest | **← the farmer** |
| `A` | Field area in hectares | ← your polygon |

Look at that table. **Two factors from the satellite, two from the farmer.** That
is the arithmetic reason the field visits aren't optional — without them you have
no `t` and no `SF_o`, and straw incorporated shortly before flooding nearly
doubles the answer.

Two numbers to remember because they're big:

- **Pre-season flooding > 30 days → SF_p = 2.41.** More than doubles the estimate.
- **Continuously flooded (1.00) → AWD (0.55).** That 0.45 gap *is* the whole
  "what if" story.

---

## The architecture decision that matters

Pulling Sentinel-1 and building a time series takes **minutes per field**. An HTTP
request must answer in **under a second**. Those don't reconcile, so you don't try:

```
BATCH (your laptop, slow, rerun often)      SERVING (always on, tiny, fast)
──────────────────────────────────────      ─────────────────────────────────
polygons → Sentinel-1 → flooded/dry              React on a cheap phone
         → season metrics                                ▲ JSON <50 ms
         → IPCC model → AWD scenario                  FastAPI (zero computation)
                   └──────► POSTGRES ◄──────────────────┘
```

The API does **no computation ever**. It's a read-only view over precomputed rows.
That's why it's fast and nearly free to host.

Say that sentence out loud in the interview — *"I separated batch from serving
because STAC queries take minutes and a web request has to return in under a
second"* — because it's real engineering judgement, not a tutorial step.

---

## What the farmer actually gets

A farmer standing in his field already knows it's flooded. Telling him that is
worthless — it's the trap every agri-tech demo falls into. What he genuinely
cannot get:

1. **An objective 120-day record** of his water regime. He can't reconstruct it
   from memory, and it's exactly what a carbon project needs as evidence.
2. **Money.** Water saved → pumping hours saved → diesel saved. This is the
   argument that moves people.
3. **Comparison.** Which fields in the village *already* dry out naturally? Those
   farmers are accidentally halfway to AWD.

The methane number is mostly for Varaha, not for him. Be honest about that
ordering.

---

## Where it's weak — say this before anyone asks

1. **12-day revisit.** A 5-day drying event is completely invisible. Your timeline
   is an interpolation. Drying-event counts are a **lower bound**.
2. **Canopy closure.** ~60 days after transplant the rice hides the water,
   backscatter climbs, and a fixed threshold starts calling flooded fields dry.
   **Biggest technical risk in the project.**
3. **Wind** roughens water and makes it look dry.
4. **EF_c carries ±40%** on its own (0.80–1.76 around 1.19).

So: good for "field A > field B" and "AWD roughly halves this." Not good for
issuing credits. **Overclaiming is what got 37 rice carbon projects invalidated** —
visible caution is itself the signal to a science team.

Hard lines: nobody gets paid for carbon from this; not decision-grade; savings as
a range with assumptions shown; never advise anyone to drain a field; anonymise
everything.

---

## The thing that can't be faked

Two field visits.

**Day 3** — 6–8 farmers. Cropping calendar, water practice, straw handling,
boundaries. Transcribe the same evening.

**Day 8** — go back holding your satellite dates and ask *"did this field dry out
around this date?"*

An honest 71% agreement beats a flattering 95%. **The disagreements are the most
valuable data you'll collect.** Everything else in this project is reproducible by
anyone with the plan. This isn't.

---

## Answering "so what did you build?"

> I built a tool that reads satellite radar to work out when rice fields in my
> district were flooded, estimates the methane that came off them, and shows a
> farmer what he'd save in water and emissions if he drained twice mid-season.
> It's deployed and running. I checked the satellite's flooding dates against what
> fifteen farmers actually told me, and I know where it disagrees and why.

That last sentence is the one nobody else can say.

---

*Deeper versions: [`docs/00-project-explainer.md`](docs/00-project-explainer.md)
for the long-form walkthrough, [`docs/03-methane-model.md`](docs/03-methane-model.md)
for every IPCC constant with its table reference.*
