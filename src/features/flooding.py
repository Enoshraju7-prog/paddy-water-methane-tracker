"""Flooded or dry? One decision per field per acquisition date.

v1 is a **fixed threshold**, deliberately. It is transparent, it is explainable
to a farmer and to an interviewer, and it gives you the labelled examples you
need to train the v2 classifier. Do not skip ahead to a model you cannot yet
validate.

    flooded  ⟺  σ⁰_VV < threshold   (default −16 dB)

Three ways this is wrong, all of which you should be able to name:

1. **Canopy closure.** ~50–70 days after transplanting the rice hides the water
   and VV rises. A fixed threshold starts calling flooded fields dry. This is
   the single biggest technical risk in the project. Mitigation here:
   `confidence` drops once NDVI says the canopy has closed.
2. **Wind.** Wind roughens the water surface and raises backscatter, so a windy
   acquisition can make a flooded field look dry.
3. **Revisit gap.** 12 days between looks. Anything shorter is invisible. Every
   "flooded" day between two flooded observations is an interpolation, and the
   drying-event count is a lower bound. Say so, every time you show a number.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import settings

# NDVI above this ≈ closed canopy, radar no longer reliably sees the water.
CANOPY_CLOSURE_NDVI = 0.55

# Within this many dB of the threshold, the call is a coin flip.
AMBIGUOUS_MARGIN_DB = 1.5


def classify(
    backscatter: pd.DataFrame,
    ndvi: pd.DataFrame | None = None,
    threshold_db: float | None = None,
) -> pd.DataFrame:
    """Add `flooded` (bool) and `confidence` ("high"/"medium"/"low") columns.

    `backscatter` — field_id, date, vv_db, vh_db (from src.data.sentinel1)
    `ndvi`        — field_id, date, ndvi (optional, from src.data.sentinel2)
    """
    threshold = threshold_db if threshold_db is not None else settings.s1_vv_flood_threshold_db

    out = backscatter.copy()
    out["date"] = pd.to_datetime(out["date"])
    out["threshold_db"] = threshold
    out["flooded"] = out["vv_db"] < threshold

    # Distance from the threshold: how much we believe the call at all.
    margin = (out["vv_db"] - threshold).abs()
    out["confidence"] = np.where(margin >= AMBIGUOUS_MARGIN_DB, "high", "medium")

    if ndvi is not None and len(ndvi):
        out = _downgrade_under_canopy(out, ndvi)

    return out.sort_values(["field_id", "date"]).reset_index(drop=True)


def _downgrade_under_canopy(obs: pd.DataFrame, ndvi: pd.DataFrame) -> pd.DataFrame:
    """Mark observations after canopy closure as low-confidence.

    We don't reclassify them — we flag them. Silently "correcting" for canopy
    with an invented threshold shift would be exactly the kind of unfalsifiable
    fudge this project is supposed to avoid. Flagging keeps it honest and gives
    the validation note something concrete to report.
    """
    ndvi = ndvi.copy()
    ndvi["date"] = pd.to_datetime(ndvi["date"])

    closure_dates = (
        ndvi[ndvi["ndvi"] >= CANOPY_CLOSURE_NDVI]
        .groupby("field_id")["date"]
        .min()
        .rename("canopy_closed_on")
    )

    obs = obs.merge(closure_dates, on="field_id", how="left")
    under_canopy = obs["canopy_closed_on"].notna() & (obs["date"] >= obs["canopy_closed_on"])
    obs.loc[under_canopy, "confidence"] = "low"
    obs["under_canopy"] = under_canopy
    return obs


def sweep_threshold(
    backscatter: pd.DataFrame,
    truth: pd.DataFrame,
    candidates: np.ndarray | None = None,
) -> pd.DataFrame:
    """Day 8 tool: agreement with farmer recall across candidate thresholds.

    `truth` — field_id, date, flooded (bool), from the validation interviews.

    Returns threshold, n, agreement, false_flooded, false_dry — so you can pick
    a threshold with the evidence in front of you and write down *why*. Report
    whatever agreement you actually get. An honest 71% beats a flattering 95%,
    and the disagreements are the most valuable rows in the table.
    """
    candidates = candidates if candidates is not None else np.arange(-20.0, -11.9, 0.5)

    truth = truth.copy()
    truth["date"] = pd.to_datetime(truth["date"])

    rows = []
    for threshold in candidates:
        predicted = classify(backscatter, threshold_db=float(threshold))
        merged = truth.merge(
            predicted[["field_id", "date", "flooded"]],
            on=["field_id", "date"],
            suffixes=("_farmer", "_satellite"),
        )
        if merged.empty:
            continue
        agree = merged["flooded_farmer"] == merged["flooded_satellite"]
        rows.append(
            {
                "threshold_db": float(threshold),
                "n": len(merged),
                "agreement": float(agree.mean()),
                # satellite said flooded, farmer said dry
                "false_flooded": int(
                    (merged["flooded_satellite"] & ~merged["flooded_farmer"]).sum()
                ),
                # satellite said dry, farmer said flooded
                "false_dry": int(
                    (~merged["flooded_satellite"] & merged["flooded_farmer"]).sum()
                ),
            }
        )
    return pd.DataFrame(rows)
