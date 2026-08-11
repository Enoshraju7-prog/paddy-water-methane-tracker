"""IPCC 2019 Refinement, Volume 4, Chapter 5.5 — rice methane, Tier 2.

Tier 2 = the IPCC equation structure with practice-specific scaling factors, as
opposed to Tier 1 (pure defaults) or Tier 3 (a process model like DNDC).

    CH4 (kg)  =  EF_i × t × A
    EF_i      =  EF_c × SF_w × SF_p × SF_o
    SF_o      =  (1 + Σ ROA_i × CFOA_i) ^ 0.59

Note where each factor comes from:

    EF_c   IPCC default
    t, A   farmer interview + your polygon
    SF_w   ← Sentinel-1     (in-season drying events)
    SF_p   ← Sentinel-1     (pre-season flooding)
    SF_o   ← farmer interview  (the satellite cannot see straw)

Two from the satellite, two from the farmer. That is the arithmetic reason the
field visits are not optional.

Every table reference below is to the 2019 Refinement. Cross-check against
docs/03-methane-model.md before changing anything.
"""

from __future__ import annotations

from enum import StrEnum

# ─────────────────────────────────────────────────────────────────────────────
# EF_c — baseline emission factor, Table 5.11
# Continuously flooded, no organic amendment. Range 0.80 – 1.76.
# ─────────────────────────────────────────────────────────────────────────────

EF_C_DEFAULT = 1.19          # kg CH4 ha^-1 day^-1
EF_C_LOW = 0.80
EF_C_HIGH = 1.76


# ─────────────────────────────────────────────────────────────────────────────
# SF_w — water regime DURING cultivation, Table 5.12  ← from Sentinel-1
# ─────────────────────────────────────────────────────────────────────────────

class WaterRegime(StrEnum):
    CONTINUOUSLY_FLOODED = "continuously_flooded"
    INTERMITTENT_SINGLE = "intermittent_single_aeration"
    INTERMITTENT_MULTIPLE = "intermittent_multiple_aeration"
    REGULAR_RAINFED = "regular_rainfed"
    DROUGHT_PRONE = "drought_prone"
    DEEP_WATER = "deep_water"


SF_W = {
    WaterRegime.CONTINUOUSLY_FLOODED: 1.00,
    WaterRegime.INTERMITTENT_SINGLE: 0.71,
    WaterRegime.INTERMITTENT_MULTIPLE: 0.55,
    WaterRegime.REGULAR_RAINFED: 0.54,
    WaterRegime.DROUGHT_PRONE: 0.16,
    WaterRegime.DEEP_WATER: 0.06,
}

# AWD, done properly, is "intermittently flooded with multiple aeration".
AWD_REGIME = WaterRegime.INTERMITTENT_MULTIPLE


def regime_from_drying_events(n_events: int) -> WaterRegime:
    """Map the satellite's drying-event count onto an IPCC water regime.

    This mapping is the single most consequential judgement call in the model,
    and it is *ours*, not the IPCC's — the guidelines describe regimes, they
    don't tell you how to detect one from radar. State it explicitly in the
    write-up.

    Because a ~12-day revisit undercounts short drying events, this is biased
    toward "continuously flooded", i.e. toward *over*-estimating methane. That
    is the conservative direction, which is the right way to be wrong here.
    """
    if n_events <= 0:
        return WaterRegime.CONTINUOUSLY_FLOODED
    if n_events == 1:
        return WaterRegime.INTERMITTENT_SINGLE
    return WaterRegime.INTERMITTENT_MULTIPLE


# ─────────────────────────────────────────────────────────────────────────────
# SF_p — water regime BEFORE cultivation (180 d prior), Table 5.13  ← Sentinel-1
# ─────────────────────────────────────────────────────────────────────────────

class PreSeasonRegime(StrEnum):
    NON_FLOODED_LT_180D = "non_flooded_less_than_180d"
    NON_FLOODED_GT_180D = "non_flooded_more_than_180d"
    FLOODED_GT_30D = "flooded_more_than_30d"
    NON_FLOODED_GT_365D = "non_flooded_more_than_365d"


SF_P = {
    PreSeasonRegime.NON_FLOODED_LT_180D: 1.00,
    PreSeasonRegime.NON_FLOODED_GT_180D: 0.89,
    PreSeasonRegime.FLOODED_GT_30D: 2.41,   # note the size of this one
    PreSeasonRegime.NON_FLOODED_GT_365D: 0.59,
}


def preseason_from_flooded_days(flooded_days: int) -> PreSeasonRegime:
    """>30 days of pre-season flooding more than doubles the emission factor."""
    if flooded_days > 30:
        return PreSeasonRegime.FLOODED_GT_30D
    return PreSeasonRegime.NON_FLOODED_LT_180D


# ─────────────────────────────────────────────────────────────────────────────
# SF_o — organic amendments, Table 5.14  ← from farmer interviews
# ─────────────────────────────────────────────────────────────────────────────

class Amendment(StrEnum):
    STRAW_SHORT = "straw_incorporated_short"   # < 30 days before cultivation
    STRAW_LONG = "straw_incorporated_long"     # > 30 days before cultivation
    COMPOST = "compost"
    FARMYARD_MANURE = "farmyard_manure"
    GREEN_MANURE = "green_manure"


CFOA = {
    Amendment.STRAW_SHORT: 1.00,     # the biggest lever a farmer controls
    Amendment.STRAW_LONG: 0.19,
    Amendment.COMPOST: 0.17,
    Amendment.FARMYARD_MANURE: 0.21,
    Amendment.GREEN_MANURE: 0.45,
}

SF_O_EXPONENT = 0.59


def sf_o(amendments: dict[Amendment, float] | None) -> float:
    """SF_o = (1 + Σ ROA_i × CFOA_i)^0.59, with ROA in t dry-weight ha⁻¹.

    No amendments → 1.0. Timing matters enormously: the same straw incorporated
    a month earlier drops CFOA from 1.00 to 0.19.
    """
    if not amendments:
        return 1.0
    total = sum(rate * CFOA[kind] for kind, rate in amendments.items())
    return (1.0 + total) ** SF_O_EXPONENT


# ─────────────────────────────────────────────────────────────────────────────
# Emission factor
# ─────────────────────────────────────────────────────────────────────────────

def emission_factor(
    regime: WaterRegime,
    preseason: PreSeasonRegime,
    amendments: dict[Amendment, float] | None = None,
    ef_c: float = EF_C_DEFAULT,
) -> float:
    """EF_i in kg CH4 ha⁻¹ day⁻¹."""
    return ef_c * SF_W[regime] * SF_P[preseason] * sf_o(amendments)


# ─────────────────────────────────────────────────────────────────────────────
# GWP
# ─────────────────────────────────────────────────────────────────────────────

GWP_CH4_AR6_NON_FOSSIL = 27.0   # project default — rice methane is biogenic
GWP_CH4_AR6_FOSSIL = 29.8
GWP_CH4_AR5 = 28.0
GWP_CH4_AR4 = 25.0
