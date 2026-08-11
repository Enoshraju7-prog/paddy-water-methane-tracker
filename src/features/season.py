"""Per-observation flooded/dry → one row of season metrics per field.

This is the bridge between the satellite and the IPCC equation. Two of the four
factors in that equation come out of this module: SF_w from the in-season
drying events, SF_p from the pre-season flooding.

Every number here carries the same caveat: a 12-day revisit means short events
are invisible. `days_flooded` is an interpolation between observations and
`n_drying_events` is a **lower bound**. Both are surfaced in the output so the
API and the UI can keep saying it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

import pandas as pd

from src.config import settings


@dataclass
class SeasonMetrics:
    field_id: str
    season_start: date
    season_end: date
    cultivation_days: int

    n_observations: int
    n_flooded_obs: int
    days_flooded: int              # interpolated between observations
    flooded_fraction: float

    n_drying_events: int           # LOWER BOUND — see module docstring
    longest_dry_spell_days: int
    first_flood_date: date | None  # proxy for transplanting/puddling

    preseason_flooded_days: int
    preseason_flooded: bool        # >30 days flooded → IPCC SF_p = 2.41

    mean_revisit_days: float       # the honesty metric: how blind are we?
    low_confidence_fraction: float


def compute(
    classified: pd.DataFrame,
    field_id: str,
    season_start: date | None = None,
    season_end: date | None = None,
) -> SeasonMetrics:
    """Season metrics for one field from its classified observation series."""
    season_start = season_start or settings.season_start
    season_end = season_end or settings.season_end
    preseason_start = season_start - timedelta(days=settings.preseason_days)

    obs = classified[classified["field_id"] == field_id].copy()
    obs["date"] = pd.to_datetime(obs["date"]).dt.date
    obs = obs.sort_values("date")

    in_season = obs[(obs["date"] >= season_start) & (obs["date"] <= season_end)]
    pre_season = obs[(obs["date"] >= preseason_start) & (obs["date"] < season_start)]

    if in_season.empty:
        raise ValueError(f"{field_id}: no observations inside the season window")

    flooded = in_season["flooded"].tolist()
    dates = in_season["date"].tolist()

    return SeasonMetrics(
        field_id=field_id,
        season_start=season_start,
        season_end=season_end,
        cultivation_days=(season_end - season_start).days,
        n_observations=len(in_season),
        n_flooded_obs=int(sum(flooded)),
        days_flooded=_interpolated_flooded_days(dates, flooded, season_start, season_end),
        flooded_fraction=float(sum(flooded) / len(flooded)),
        n_drying_events=_count_drying_events(flooded),
        longest_dry_spell_days=_longest_dry_spell(dates, flooded),
        first_flood_date=next((d for d, f in zip(dates, flooded, strict=True) if f), None),
        preseason_flooded_days=_interpolated_flooded_days(
            pre_season["date"].tolist(),
            pre_season["flooded"].tolist(),
            preseason_start,
            season_start,
        ),
        preseason_flooded=_interpolated_flooded_days(
            pre_season["date"].tolist(),
            pre_season["flooded"].tolist(),
            preseason_start,
            season_start,
        ) > 30,
        mean_revisit_days=_mean_revisit(dates),
        low_confidence_fraction=float(
            (in_season.get("confidence", pd.Series(dtype=str)) == "low").mean()
        ) if "confidence" in in_season else 0.0,
    )


def compute_all(classified: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Season metrics for every field present in `classified`."""
    return pd.DataFrame(
        asdict(compute(classified, field_id, **kwargs))
        for field_id in sorted(classified["field_id"].unique())
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────

def _interpolated_flooded_days(
    dates: list[date], flooded: list[bool], window_start: date, window_end: date
) -> int:
    """Days flooded, holding each observation's state until the next one.

    Nearest-neighbour in time — the simplest defensible interpolation. A linear
    or midpoint rule would look more sophisticated without being more true: we
    genuinely have no information between passes.
    """
    if not dates:
        return 0

    total = 0
    for i, (d, is_flooded) in enumerate(zip(dates, flooded, strict=True)):
        start = max(d, window_start)
        end = dates[i + 1] if i + 1 < len(dates) else window_end
        end = min(end, window_end)
        if is_flooded and end > start:
            total += (end - start).days
    return total


def _count_drying_events(flooded: list[bool]) -> int:
    """Runs of consecutive dry observations, each ≥ min_obs_for_drying_event.

    Leading dry observations (before the field is ever flooded) are not drying
    events — the field just hadn't been puddled yet. Only count a dry run once
    we have seen water.
    """
    events = 0
    run = 0
    seen_water = False

    for is_flooded in flooded:
        if is_flooded:
            seen_water = True
            if run >= settings.min_obs_for_drying_event:
                events += 1
            run = 0
        elif seen_water:
            run += 1

    # A dry run at the end of the season is harvest drainage, not mid-season
    # aeration, so it is deliberately not counted.
    return events


def _longest_dry_spell(dates: list[date], flooded: list[bool]) -> int:
    longest = 0
    run_start: date | None = None

    for i, (d, is_flooded) in enumerate(zip(dates, flooded, strict=True)):
        if not is_flooded:
            run_start = run_start or d
            run_end = dates[i + 1] if i + 1 < len(dates) else d
            longest = max(longest, (run_end - run_start).days)
        else:
            run_start = None
    return longest


def _mean_revisit(dates: list[date]) -> float:
    """Average gap between usable observations — your blindness, quantified.

    ~12 days is normal for a single Sentinel-1 orbit. Much more than that means
    you lost scenes somewhere and your metrics are shakier than they look.
    """
    if len(dates) < 2:
        return float("nan")
    gaps = [(b - a).days for a, b in zip(dates, dates[1:], strict=True)]
    return sum(gaps) / len(gaps)
