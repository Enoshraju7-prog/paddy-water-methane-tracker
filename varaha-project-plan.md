# 14 Days — Paddy Water & Methane Tracker (v1)

**Study area:** a couple of mandals in the East Godavari region, Andhra Pradesh
**Goal:** a deployed, working tool that a real farmer or extension worker can open on a phone — and the first version of something you keep building.

---

## First, an honest question

Before designing anything: **what does satellite data actually give a rice farmer that he doesn't already have?**

A farmer standing in his field knows whether it's flooded. He knows his own transplanting date. Telling him "your field is under water" is worthless — this is the trap most agri-tech demos fall into.

Here is what he genuinely can't get on his own:

1. **A record of the whole season.** What his water regime looked like across all 120 days, as an objective log. He can't reconstruct that from memory, and it's the exact thing a carbon project needs as evidence.
2. **A number attached to the practice.** "Your field emitted roughly X tonnes CO₂e this season. If you had drained twice mid-season, it would have been Y." That converts an abstraction into something concrete.
3. **Money, not carbon.** Water saved → pumping hours saved → diesel or electricity saved. That's the argument that actually moves a farmer, and it's real: AWD saves roughly 30% of water.
4. **Comparison across fields.** Which fields in the village already dry out naturally? Those farmers are already doing something close to AWD and don't know it.

**Points 1 and 3 are the useful ones.** Build for those. Point 2 is what makes it a Varaha project.

---

## What v1 actually is

**A web app where you pick a field on a map and see its water and methane story for the season.**

For each field:
- A **water timeline** for the season — flooded / dry, day by day, derived from satellite radar
- **Estimated methane emissions** for the season, in tonnes CO₂e
- A **"what if you used AWD"** comparison: methane avoided, water saved, approximate pumping cost saved
- A **season record card** the farmer can screenshot and keep

Interface in **Telugu and English**. You've already shipped a Telugu-speaking voice agent for MM Car Care — you know this matters and you know how to do it.

Not an app store app. A mobile-friendly web page with a URL, deployed, that works on a ₹8,000 Android phone over patchy 4G. That constraint should drive your design decisions: small payloads, no heavy map tiles, works if it loads slowly.

---

## The architecture decision that matters

**Precompute everything offline. Serve pre-baked results.**

Pulling Sentinel-1 imagery and computing a backscatter time series takes minutes per field. You cannot do that inside a web request — the page would time out and the costs would be silly.

So two separate pieces:

**1. The pipeline (batch, runs on your laptop or a scheduled job)**
Fetch Sentinel-1 → detect flooding per field per date → run the methane model → write results to a database. Runs weekly, or once per season for v1.

**2. The app (always on, tiny, fast)**
FastAPI + Postgres + a small React or plain-HTML map front end. Every request is just a database read. Responses in milliseconds, hosting costs near zero.

Say this out loud in the interview — *"I separated batch processing from serving because STAC queries take minutes and a web request has to return in under a second"* — because that's a real engineering judgement, not a tutorial step.

**Deploy on Azure Container Apps.** You've already done exactly this for the invoice review app: Docker image → Azure Container Registry → Container Apps. Reuse what you know. Don't learn a new cloud in a fortnight.

---

## The data

| What | Source | Cost |
|---|---|---|
| Flooding detection | **Sentinel-1 GRD** via Microsoft Planetary Computer | Free |
| Crop stage | Sentinel-2 L2A, clear days only | Free |
| Weather | NASA POWER API | Free, no key |
| Soil | SoilGrids (ISRIC) | Free |
| **Field boundaries** | **You draw them** | Your time |
| **Farming practice** | **Farmer interviews** | Your time |

Radar rather than optical because your season is the monsoon and optical imagery will be under cloud for most of it. Radar sees through cloud, and flooded fields come back dark because smooth water bounces the signal away from the satellite.

**Field boundaries:** for 25–40 fields, walk the boundary with a phone GPS app, or draw polygons over satellite basemap in QGIS using landmarks the farmer points out. Both are fine. This is slow, manual and unglamorous — and it's exactly what "aggregating fragmented smallholdings" means in practice.

---

## The 14 days

**Days 1–2 — Geospatial foundations.** CRS (why you can't measure area in degrees; UTM 44N / EPSG:32644 for this region), vector vs raster, GeoPandas and Rasterio basics. Ship: load a boundary, clip a raster, save a GeoTIFF.

**Day 3 — Field visit 1.** 6–8 farmers. Learn the cropping calendar, water practice, straw handling, whether they control their own irrigation. Capture field boundaries. Transcribe the same evening.

**Days 4–5 — Data layer.** One module per source, each taking a bounding box and date range. Cache every download to disk. Ship: one command populates `data/raw/`.

**Days 6–7 — Flooding detection.** Sentinel-1 VV backscatter time series per field, thresholded into flooded / dry, converted to season metrics: days flooded, number of drying events, pre-season flooding. Ship: a chart per field with flooded periods shaded. **This is the heart of the project — if it isn't working by Day 7, stop adding scope and fix it.**

**Day 8 — Field visit 2.** Go back with your satellite-derived dates and ask directly: *"did this field dry out around this date?"* Record agreement and disagreement honestly. The disagreements are your most valuable data, and an honest accuracy figure beats a flattering one.

**Day 9 — The models.** Methane via the IPCC 2019 Refinement Tier 2 approach: baseline emission factor × cultivation days × scaling factors for water regime during season (from radar), pre-season water regime (from radar), and organic amendments (from farmers). Then the AWD scenario, and the water/pumping-cost saving.

**Days 10–11 — Backend.** FastAPI + Postgres. Schema: fields, observations, season results. Endpoints: list fields, get one field's timeline, get its scenario comparison. Load your precomputed results in.

**Day 12 — Front end.** Mobile-first map, tap a field, see its card. Telugu and English toggle. Keep it plain and fast.

**Day 13 — Deploy and test with a real person.** Docker → ACR → Azure Container Apps. Then **show it to one farmer on your own phone** and write down every confusion, every question, everything he ignored. That paragraph will be the most compelling thing in your whole application.

**Day 14 — Write up and rehearse.** README with a pipeline diagram, a short validation note (satellite vs farmer accuracy, limitations), and the roadmap below. Rehearse the walkthrough out loud twice.

**Cut list if you fall behind, in this order:** the scenario comparison, then the Telugu toggle, then the map (a dropdown of field names works), then RothC soil carbon (which is already a stretch, not core). **Never cut the field visits or the deployment** — those are the two things that make this yours.

---

## What you must not promise

You'll be showing this to real farmers, so be careful:

- **Don't imply anyone will get paid for carbon.** They won't, from this. Say plainly it's a student project.
- **Don't present the numbers as decision-grade.** A 12-day satellite revisit can miss a short drying event entirely. Say so.
- **Give cost savings as a range**, and show your assumptions on pumping hours and rates.
- **Don't advise anyone to drain their field.** AWD done wrong loses yield. You're showing information, not agronomic advice.
- **Anonymise.** Farmer 1, Farmer 2. No names, no plot numbers, approximate locations only in the public repo. Say in the write-up that you did this.

Being visibly careful about this is itself a signal to a science team. Overclaiming is the thing that got 37 rice carbon projects invalidated.

---

## Where it goes after v1

You said you want to keep building. Have this ready — it's a strong interview answer on its own, because it shows you think in versions rather than demos.

**v2 — More fields, better classifier.** Replace the fixed radar threshold with a trained classifier using your farmer-validated labels. Expand from 30 fields to a few hundred. Add multi-season history.

**v3 — Farmer-facing loop.** A farmer confirms or corrects what the satellite saw, straight in the app. Now you have a growing ground-truth dataset — which is the genuinely valuable asset here, and the thing nobody can copy.

**v4 — Soil carbon.** Add RothC, so you cover both the VM0042 (soil carbon) and VM0051 (rice methane) sides.

**v5 — Aggregation.** Group fields into a project boundary, compute a project-level total with uncertainty, and produce a report in the shape a registry expects. That's Varaha's actual product.

The honest version of the arc: v1 is a student prototype. v3 is where it becomes something real, because that's where the data starts compounding.

---

## Answering "so what did you build?"

> I built a tool that reads satellite radar to work out when rice fields in my district were flooded, estimates the methane that came off them, and shows a farmer what he'd save in water and emissions if he drained twice mid-season. It's deployed and running. I checked the satellite's flooding dates against what fifteen farmers actually told me, and I know where it disagrees and why.

That's a better answer than anyone else will give, because the last sentence can't be faked.
