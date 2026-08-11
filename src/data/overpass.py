"""When does Sentinel-1 fly over? The calendar that makes same-day validation possible.

Normally you validate a satellite product by asking people what they remember.
Recall is weak, and everyone knows it, which is why most validation sections are
unconvincing.

There is a much better option available here, because the satellite flies a fixed,
published schedule. If you know the next pass date, you can **stand in the field on
that day** and record flooded or dry with a timestamped photo. That is a zero-recall
ground-truth point, and it costs nothing but timing.

This module works out those dates. It does two things:

1. Looks at the actual archive over your bbox to find the observed pass dates and
   the real cadence — **derived, not assumed**. Sentinel-1A alone gives a 12-day
   repeat, but with Sentinel-1C operational since 2025 some areas now get 6-day
   coverage. Worth knowing which one you have; it doubles your validation budget.
2. Projects that cadence forward so you can plan trips.

    python -m src.data.overpass                 # next 8 weeks
    python -m src.data.overpass --weeks 16
    python -m src.data.overpass --orbit any     # both ascending and descending
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import typer

from src.config import settings

# GRD rather than RTC here, deliberately. RTC is the better product for
# *backscatter* (terrain-corrected, calibrated) and is what src/data/sentinel1.py
# uses — but its processing lags and it drops scenes. GRD is the more complete
# record of when the satellite actually flew, and for a calendar the acquisition
# date is all we need. Checked over Apr–Jul 2026: GRD had a pass (6 June) that
# RTC was missing.
COLLECTION = "sentinel-1-grd"
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Sentinel-1 crosses the equator at a fixed local solar time. Descending passes
# are morning, ascending are evening. Useful for planning what time to be there.
TYPICAL_LOCAL_TIME = {"descending": "~06:00 IST", "ascending": "~18:00 IST"}

app = typer.Typer(add_completion=False)


@dataclass
class Pass:
    date: date
    orbit_direction: str
    relative_orbit: int
    platform: str

    def __str__(self) -> str:
        return (f"{self.date:%a %d %b %Y}  {self.orbit_direction:<10} "
                f"orbit {self.relative_orbit:<3} {self.platform}")


def observed_passes(
    bbox: tuple[float, float, float, float] | None = None,
    start: date | None = None,
    end: date | None = None,
    orbit_direction: str | None = None,
) -> list[Pass]:
    """Pass dates actually present in the archive over the bbox."""
    import planetary_computer
    import pystac_client

    bbox = bbox or settings.bbox
    end = end or date.today()
    start = start or (end - timedelta(days=90))
    orbit_direction = orbit_direction or settings.s1_orbit_direction

    catalog = pystac_client.Client.open(
        STAC_URL, modifier=planetary_computer.sign_inplace
    )
    items = list(
        catalog.search(
            collections=[COLLECTION],
            bbox=list(bbox),
            datetime=f"{start}/{end}",
        ).items()
    )

    passes: dict[tuple, Pass] = {}
    for item in items:
        props = item.properties
        direction = props.get("sat:orbit_state", "unknown")
        if orbit_direction != "any" and direction != orbit_direction:
            continue

        acquired = datetime.fromisoformat(
            props["datetime"].replace("Z", "+00:00")
        ).date()
        relative = props.get("sat:relative_orbit", -1)
        platform = props.get("platform", "sentinel-1?")

        # One scene per (date, orbit) — a bbox often spans several tiles.
        passes[(acquired, relative)] = Pass(acquired, direction, relative, platform)

    return sorted(passes.values(), key=lambda p: p.date)


def infer_cadence(passes: list[Pass]) -> dict[int, int]:
    """Observed repeat interval in days, per relative orbit.

    Derived rather than assumed — but derived carefully. Two things corrupt a
    naive estimate, and both are real in this archive:

    * **Platform handovers.** When one satellite takes over a relative orbit
      from another (Sentinel-1A → Sentinel-1D on orbit 19 in June 2026), the
      changeover produces a single short gap — 7 days rather than 12. Taking
      the *minimum* gap treats that artefact as the cycle and projects a
      schedule that is wrong for every future date.
    * **Missing scenes.** Processing gaps produce occasional double-length
      gaps (24 days instead of 12).

    So we take the **mode** — the gap that occurs most often — which survives
    both. Ties break toward the smaller gap.
    """
    from collections import Counter

    by_orbit: dict[int, list[date]] = defaultdict(list)
    for p in passes:
        by_orbit[p.relative_orbit].append(p.date)

    cadence = {}
    for relative, dates in by_orbit.items():
        dates = sorted(set(dates))
        if len(dates) < 2:
            continue
        gaps = [(b - a).days for a, b in zip(dates[:-1], dates[1:], strict=True)]
        counts = Counter(gaps)
        top = max(counts.values())
        cadence[relative] = min(g for g, n in counts.items() if n == top)
    return cadence


def platform_handovers(passes: list[Pass]) -> list[tuple[date, str, str]]:
    """Points where a different satellite took over a relative orbit.

    Worth surfacing: a handover shifts the pass day-of-week permanently, so a
    calendar computed before one is wrong after it.
    """
    handovers = []
    by_orbit: dict[int, list[Pass]] = defaultdict(list)
    for p in passes:
        by_orbit[p.relative_orbit].append(p)

    for orbit_passes in by_orbit.values():
        ordered = sorted(orbit_passes, key=lambda p: p.date)
        for prev, nxt in zip(ordered[:-1], ordered[1:], strict=True):
            if prev.platform != nxt.platform:
                handovers.append((nxt.date, prev.platform, nxt.platform))
    return sorted(handovers)


def project_forward(
    passes: list[Pass], weeks: int = 8, from_date: date | None = None
) -> list[Pass]:
    """Extrapolate each relative orbit forward using its observed cadence."""
    from_date = from_date or date.today()
    horizon = from_date + timedelta(weeks=weeks)
    cadence = infer_cadence(passes)

    latest: dict[int, Pass] = {}
    for p in passes:
        if p.relative_orbit not in latest or p.date > latest[p.relative_orbit].date:
            latest[p.relative_orbit] = p

    upcoming = []
    for relative, last in latest.items():
        repeat = cadence.get(relative)
        if not repeat:
            continue
        nxt = last.date + timedelta(days=repeat)
        while nxt <= horizon:
            if nxt >= from_date:
                upcoming.append(
                    Pass(nxt, last.orbit_direction, relative, last.platform)
                )
            nxt += timedelta(days=repeat)

    return sorted(upcoming, key=lambda p: p.date)


@app.command()
def main(
    weeks: int = typer.Option(14, help="How far ahead to project."),
    lookback: int = typer.Option(
        180, help="Days of archive to learn the cadence from. Needs enough passes "
                  "for the modal gap to be meaningful."
    ),
    orbit: str = typer.Option(None, help="descending | ascending | any"),
) -> None:
    from rich import print as rprint
    from rich.table import Table

    orbit = orbit or settings.s1_orbit_direction
    today = date.today()

    rprint(f"[bold]Sentinel-1 overpass calendar[/bold]  bbox {settings.bbox}")
    rprint(f"[dim]{COLLECTION} · orbit {orbit} · last {lookback} days[/dim]\n")

    past = observed_passes(
        start=today - timedelta(days=lookback), end=today, orbit_direction=orbit
    )
    if not past:
        rprint("[red]No scenes found.[/red] Try --orbit any, or widen the bbox.")
        raise typer.Exit(1)

    cadence = infer_cadence(past)
    rprint(f"[bold]Observed:[/bold] {len(past)} passes over {lookback} days")
    for relative, days in sorted(cadence.items()):
        rprint(f"  relative orbit {relative}: repeats every [bold]{days}[/bold] days")

    for when, old, new in platform_handovers(past):
        rprint(
            f"\n[yellow]Platform handover {when:%d %b %Y}:[/yellow] {old} → {new}. "
            f"The pass day-of-week shifted here — any calendar computed before "
            f"this date is wrong after it."
        )

    if len(cadence) > 1:
        rprint(
            f"\n[green]{len(cadence)} orbits cover this area[/green] — the effective "
            f"revisit is better than any single orbit's cycle."
        )
    elif cadence:
        only = next(iter(cadence.values()))
        rprint(f"\n[yellow]One orbit only — {only}-day revisit.[/yellow] "
               f"Drying events shorter than that are invisible, so your "
               f"drying-event count is a lower bound.")

    upcoming = project_forward(past, weeks=weeks, from_date=today)
    if not upcoming:
        rprint("[yellow]Could not project forward — not enough history.[/yellow]")
        raise typer.Exit(1)

    table = Table(title=f"Next {weeks} weeks — plan trips around these")
    table.add_column("date")
    table.add_column("in")
    table.add_column("orbit")
    table.add_column("rel")
    table.add_column("be there")

    for p in upcoming:
        days_away = (p.date - today).days
        soon = days_away <= 7
        table.add_row(
            f"[bold]{p.date:%a %d %b}[/bold]" if soon else f"{p.date:%a %d %b}",
            "TODAY" if days_away == 0 else f"{days_away}d",
            p.orbit_direction,
            str(p.relative_orbit),
            TYPICAL_LOCAL_TIME.get(p.orbit_direction, "?"),
        )
    rprint(table)

    nxt = upcoming[0]
    away = (nxt.date - today).days
    when = "TODAY" if away == 0 else "tomorrow" if away == 1 else f"in {away} days"
    rprint(
        f"\n[bold green]Next pass: {nxt.date:%A %d %B} — {when}[/bold green] "
        f"({TYPICAL_LOCAL_TIME.get(nxt.orbit_direction, '?')})"
    )

    season_end = settings.season_2026_end
    remaining = [p for p in upcoming if p.date <= season_end]
    rprint(
        f"\n[bold]{len(remaining)} passes[/bold] before the 2026 season ends "
        f"({season_end:%d %b}). Each one you miss is ground truth you cannot recover."
    )
    rprint(
        "[dim]These are projections from the observed cycle, not a published "
        "schedule. Re-run a few days before travelling to confirm.[/dim]"
    )


if __name__ == "__main__":
    app()
