"""Water saved → pumping hours saved → rupees. As a range, with assumptions shown.

Of everything this project computes, **this is the number a farmer actually
cares about**. Methane is for Varaha. Money is for him.

It is also the crudest thing in the repo, and that has to be visible rather than
hidden. Every default below is a placeholder until you replace it with something
a farmer told you in Visit 1: his pump's horsepower, how many hours he runs it
per irrigation, how many irrigations per season, and what he pays.

One thing you may well find in Andhra Pradesh: **farm electricity is heavily
subsidised**, often effectively free. If that is true for your farmers, the cost
saving collapses toward zero and the honest thing is to report that — a real
finding that the money argument doesn't work here beats a fabricated saving.
Water scarcity and pump runtime may still matter to him even when the tariff
doesn't; ask.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import settings


@dataclass
class WaterResult:
    field_id: str
    area_ha: float

    seasonal_water_m3: float
    water_saved_m3_low: float
    water_saved_m3_high: float

    pump_hours_saved_low: float
    pump_hours_saved_high: float

    cost_saved_inr_low: float
    cost_saved_inr_high: float

    assumptions: dict[str, float | str]


def estimate(
    field_id: str,
    area_ha: float,
    seasonal_irrigation_mm: float | None = None,
    pump_discharge_m3_per_hour: float | None = None,
    cost_per_pump_hour_inr: float | None = None,
) -> WaterResult:
    """AWD water and cost saving for one field, as a low–high range."""
    irrigation_mm = seasonal_irrigation_mm or settings.seasonal_irrigation_mm
    discharge = pump_discharge_m3_per_hour or settings.pump_discharge_m3_per_hour
    cost_per_hour = (
        cost_per_pump_hour_inr
        if cost_per_pump_hour_inr is not None
        else settings.cost_per_pump_hour_inr
    )

    # 1 mm over 1 ha = 10 m³.
    seasonal_m3 = irrigation_mm * area_ha * 10.0

    saved_low = seasonal_m3 * settings.awd_water_saving_low
    saved_high = seasonal_m3 * settings.awd_water_saving_high

    hours_low = saved_low / discharge
    hours_high = saved_high / discharge

    return WaterResult(
        field_id=field_id,
        area_ha=round(area_ha, 4),
        seasonal_water_m3=round(seasonal_m3, 1),
        water_saved_m3_low=round(saved_low, 1),
        water_saved_m3_high=round(saved_high, 1),
        pump_hours_saved_low=round(hours_low, 1),
        pump_hours_saved_high=round(hours_high, 1),
        cost_saved_inr_low=round(hours_low * cost_per_hour, 0),
        cost_saved_inr_high=round(hours_high * cost_per_hour, 0),
        # Shipped with the result so the UI can print them next to the number.
        # A savings figure without its assumptions is not information.
        assumptions={
            "seasonal_irrigation_mm": irrigation_mm,
            "awd_saving_fraction": f"{settings.awd_water_saving_low:.0%}"
                                   f"–{settings.awd_water_saving_high:.0%}",
            "pump_discharge_m3_per_hour": discharge,
            "cost_per_pump_hour_inr": cost_per_hour,
            "source": "placeholder defaults — replace with field-visit values",
        },
    )
