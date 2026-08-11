# Field visit kit

Print this, or keep it open on your phone. Telugu phrasing below is a starting
point — **adjust it to how people actually speak in your mandal.** You know the
local register; I don't.

---

## Trip 1 — rapport and selection

The goal of Trip 1 is **not data**. It is that six to eight farmers know who you
are and don't mind you coming back. Everything else is a bonus.

If you extract a full dataset on day one and nobody wants to see you again, the
project is dead — Phase 5 needs repeat visits during the live season, and those
only happen if the first visit was pleasant.

### Before you leave

- [ ] Phone charged, plus a power bank
- [ ] GPS app installed and tested (**GPS Fields Area Measure**, or **OsmAnd**)
- [ ] Tablet or large phone with a satellite basemap of the area **downloaded
      offline** — signal in the fields is unreliable
- [ ] This document, printed
- [ ] Notebook and pen (batteries die; paper doesn't)
- [ ] Voice recorder app ready — but **ask before recording**

---

## Say this first, every time

Before any question. Don't skip it because it feels awkward — the awkwardness is
the point, it's what makes the consent real.

> నమస్కారం. నా పేరు ఏనోష్. నేను విద్యార్థిని.
>
> వరి పొలాల్లో నీరు ఎప్పుడు నిలిచి ఉంటుంది అనేది **ఉపగ్రహం** (satellite) ద్వారా
> తెలుసుకునే ప్రాజెక్ట్ చేస్తున్నాను.
>
> **ఇది చదువు కోసం మాత్రమే చేసే ప్రాజెక్ట్.** దీని వల్ల మీకు డబ్బు కానీ, కార్బన్
> క్రెడిట్ కానీ ఏమీ రావు. నేను ఏమీ అమ్మడం లేదు, ఏ కంపెనీ తరపునా రాలేదు.
>
> మీ **పేరు కానీ, సర్వే నంబర్ కానీ** ఎక్కడా రాయను. "రైతు 1", "రైతు 2" అని
> మాత్రమే రాసుకుంటాను.
>
> మీరు చెప్పే విషయాలు నా ప్రాజెక్ట్ రిపోర్ట్‌లో వాడుకోవచ్చా?

**English, for the record:**

> My name is Enosh, I'm a student. I'm doing a project that uses satellites to work
> out when rice fields have water standing in them.
>
> This is only a student project. You will not get money or carbon credits from it.
> I'm not selling anything and I'm not here on behalf of any company.
>
> I won't write down your name or survey number anywhere — only "Farmer 1",
> "Farmer 2".
>
> May I use what you tell me in my project report?

**Write down the answer.** If it's no, that's fine — thank them and move on.

---

## The questions

Nine questions. Ask about **both seasons** — 2026 (happening now) and 2025 (what
the pipeline is built on). Don't read them like a form; work them into conversation.

### Cropping calendar → gives you `t`

**1.** ఈ పొలంలో ఈ సంవత్సరం నారు ఎప్పుడు నాటారు?
*When did you transplant this season (2026)?*

**2.** కోత ఎప్పుడు అవుతుంది అనుకుంటున్నారు?
*When do you expect to harvest?*

**3.** గత సంవత్సరం (2025) ఎప్పుడు నాటారు, ఎప్పుడు కోశారు?
*Last year — when did you transplant and harvest?*

> Expect vagueness on 2025, and note how vague. "Around Dasara" is a real answer
> and you can convert it to a date later. **Record their words, not your
> interpretation.**

### Straw → gives you `SF_o`, the biggest lever the farmer controls

**4.** కోత తర్వాత గడ్డి ఏం చేస్తారు? పొలంలోనే కలుపుతారా, కాల్చేస్తారా, లేక
తీసేస్తారా?
*After harvest, what happens to the straw — incorporated, burned, or removed?*

**5.** గడ్డి కలిపిన **ఎన్ని రోజుల తర్వాత** నీరు పెడతారు?
*How many days after incorporating the straw do you flood the field?*

> Question 5 matters more than it looks. Under 30 days → CFOA 1.00. Over 30 days →
> 0.19. That single answer can change the methane estimate by a factor of two.
> If they say "we burn it", SF_o = 1.0 and there's no amendment at all.

### Water → validates `SF_w`

**6.** నీరు మీ ఇష్టప్రకారం పెట్టుకోగలరా? లేక కాలువ షెడ్యూల్ ప్రకారం వస్తుందా?
*Do you control your own watering, or does the canal schedule decide?*

> If the canal decides, **AWD may not even be possible for him** — which is a
> genuinely important finding for the write-up, and one most demos never surface.

**7.** సీజన్ మధ్యలో పొలం ఎప్పుడైనా ఆరిపోయిందా? ఎప్పుడు, ఎన్ని రోజులు?
*Did the field dry out mid-season at any point? When, and for how long?*

### Money → the water model

**8.** పంపు ఎన్ని హార్స్ పవర్? ఒకసారి నీరు పెట్టడానికి ఎన్ని గంటలు నడుపుతారు?
సీజన్‌లో ఎన్నిసార్లు?
*Pump horsepower? Hours per irrigation? How many irrigations per season?*

**9.** కరెంటు బిల్లు / డీజిల్ ఖర్చు ఎంత అవుతుంది?
*What do you pay for electricity or diesel?*

> **If the answer is "free" or "almost nothing"** — farm power in AP is heavily
> subsidised — then the cost-saving argument collapses. **Report that.** A finding
> that the money argument doesn't work here is worth more than a made-up number.
> Follow up: does running the pump cost him anything else — time, waiting for
> supply, labour?

---

## Boundary capture

**Walk 5 fields, draw all of them.** The overlap gives you a measured error.

### Walking (5 fields)

1. Open the GPS area app, start a new plot
2. Walk the bund, all the way round, at a steady pace
3. Close the loop, save as `F001_walked`, export GeoJSON or KML
4. Note the accuracy figure the app reports (usually ±3–5 m)

### Drawing (all fields, including the 5 walked)

1. Satellite basemap on the tablet, zoomed to the field
2. **Let the farmer point.** He knows where the bund actually runs, and where it
   moved last year. This is also a good conversation — it makes him a participant
   rather than a subject.
3. Trace the polygon, save as `F001_drawn`

Paddy plots in the delta are visually obvious — bunded rectangles with hard edges.
Drawing is often *more* accurate than a phone GPS for a 0.4 ha plot.

### Naming

**Anonymous from the very first file.** `F001`, `F002`… and `Farmer 1`,
`Farmer 2`. Never a name, never a survey number, not even in a temporary file.
Keep any name↔ID mapping offline, on paper, out of the repo.

---

## Trip 2+ — same-day validation

This is the strongest thing in the project. Short visits, timed to satellite passes.

**Before you go:** run the overpass calendar (Phase 3) and pick a pass date.

On that day, for each field you can reach:

| Field | Record |
|---|---|
| `field_id` | F001 |
| `date` | the pass date |
| `observed_flooded` | yes / no |
| `water_depth_cm` | rough — 0, 2, 5, 10 |
| `photo` | timestamped, GPS on |
| `notes` | "just drained yesterday", "rained hard this morning" |

That's it. Ten minutes per field. **Turn on GPS tagging in the camera app** before
you start — an untagged photo is much weaker evidence.

The notes column is where the value hides. "Drained yesterday" explains a
disagreement that would otherwise look like a model failure.

### Also, while you're there

Read back 2–3 satellite-derived dates from 2025:

> ఈ పొలం **సెప్టెంబర్ 12 తారీఖు దగ్గర** ఆరిపోయిందా?
> *Did this field dry out around 12 September?*

Record agreement **and disagreement**. Don't lead the witness — if he hesitates,
write "unsure". "Unsure" is data.

---

## What you must not say

- ❌ "You'll get carbon credits" / "You'll get paid" — **no.**
- ❌ "You should drain your field" — you are not an agronomist and AWD done wrong
  loses yield. You show information; you don't advise.
- ❌ "The satellite says you're wrong" — when it disagrees, **the satellite is the
  one on trial**, not the farmer. He was standing in the field.
- ❌ Any promise about a future visit you're not certain you'll make.

---

## Same evening

Non-negotiable. Do it before you sleep.

- [ ] Transcribe notes while you still remember the gestures and the tone
- [ ] Export GPS traces off the phone
- [ ] Photos into `data/fields/photos/` (gitignored)
- [ ] Fill in `data/fields/interviews.csv`
- [ ] Write one paragraph of **impressions** — what surprised you, what didn't fit
      your assumptions

That last paragraph is worth more than the CSV. It's where the interesting
observations live, and you will not remember them in a week.
