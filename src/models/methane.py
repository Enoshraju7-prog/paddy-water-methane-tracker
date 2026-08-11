"""Per-field seasonal methane, and the AWD counterfactual.

Baseline uses the water regime the satellite actually observed. The AWD scenario
re-runs the same equation with SF_w forced to "intermittent, multiple aeration".
Everything else is held constant — same field, same season length, same straw.

If a field is *already* intermittently flooded, the avoided figure comes out
small or zero. That is not a failure of the model; it is the most interesting
result you can show a farmer: *"you are already doing most of this."*
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import settings
from src.models.ipcc import (
    AWD_REGIME,
    EF_C_HIGH,
    EF_C_LOW,
    Amendment,
    PreSeasonRegime,
    WaterRegime,
    emission_factor,
    preseason_from_flooded_days,
    regime_from_drying_events,
)


@dataclass
class MethaneResult:
    field_id: str
    area_ha: float
    cultivation_days: int

    water_regime: str
    preseason_regime: str
    sf_o_value: float
    emission_factor_kg_ha_day: float

    ch4_kg: float
    co2e_tonnes: float
    co2e_tonnes_low: float      # EF_c = 0.80
    co2e_tonnes_high: float     # EF_c = 1.76

    # AWD counterfactual
    awd_ch4_kg: float
    awd_co2e_tonnes: float
    co2e_avoided_tonnes: float
    pct_reduction: float

    gwp_used: float


def estimate(
    field_id: str,
    area_ha: float,
    cultivation_days: int,
    n_drying_events: int,
    preseason_flooded_days: int,
    amendments: dict[Amendment, float] | None = None,
    gwp: float | None = None,
) -> MethaneResult:
    """Baseline + AWD scenario for one field.

    `n_drying_events` and `preseason_flooded_days` come from
    src.features.season; `amendments` comes from the farmer interview.
    """
    gwp = gwp if gwp is not None else settings.gwp_ch4

    regime = regime_from_drying_events(n_drying_events)
    preseason = preseason_from_flooded_days(preseason_flooded_days)

    from src.models.ipcc import sf_o as _sf_o

    ef = emission_factor(regime, preseason, amendments, ef_c=settings.ef_c_baseline)
    ch4_kg = ef * cultivation_days * area_ha

    ef_awd = emission_factor(AWD_REGIME, preseason, amendments, ef_c=settings.ef_c_baseline)
    awd_ch4_kg = ef_awd * cultivation_days * area_ha

    def to_co2e(kg: float) -> float:
        return kg / 1000.0 * gwp

    co2e = to_co2e(ch4_kg)
    awd_co2e = to_co2e(awd_ch4_kg)

    # Uncertainty from EF_c alone (±~40%). It is not the only source — SF_w
    # rests on an undercounted drying-event count and SF_o on recall — but it
    # is the only one with a published range, so it is the only one we quantify.
    low = to_co2e(
        emission_factor(regime, preseason, amendments, ef_c=EF_C_LOW)
        * cultivation_days * area_ha
    )
    high = to_co2e(
        emission_factor(regime, preseason, amendments, ef_c=EF_C_HIGH)
        * cultivation_days * area_ha
    )

    return MethaneResult(
        field_id=field_id,
        area_ha=round(area_ha, 4),
        cultivation_days=cultivation_days,
        water_regime=str(regime),
        preseason_regime=str(preseason),
        sf_o_value=round(_sf_o(amendments), 4),
        emission_factor_kg_ha_day=round(ef, 4),
        ch4_kg=round(ch4_kg, 2),
        co2e_tonnes=round(co2e, 3),
        co2e_tonnes_low=round(low, 3),
        co2e_tonnes_high=round(high, 3),
        awd_ch4_kg=round(awd_ch4_kg, 2),
        awd_co2e_tonnes=round(awd_co2e, 3),
        co2e_avoided_tonnes=round(max(co2e - awd_co2e, 0.0), 3),
        pct_reduction=round(100.0 * max(co2e - awd_co2e, 0.0) / co2e, 1) if co2e else 0.0,
        gwp_used=gwp,
    )


def parse_amendments(
    straw_management: str | None, days_before_flooding: int | None, rate_t_ha: float = 4.0
) -> dict[Amendment, float] | None:
    """Turn a farmer's answer into an IPCC amendment dict.

    `rate_t_ha` default of 4 t/ha is a typical residue load for a rice crop —
    replace it with what farmers actually tell you. If they burn or remove the
    straw, there is no amendment at all and SF_o = 1.0.
    """
    if not straw_management or straw_management in {"removed", "burned", "none"}:
        return None

    if straw_management == "incorporated":
        kind = (
            Amendment.STRAW_SHORT
            if (days_before_flooding is None or days_before_flooding < 30)
            else Amendment.STRAW_LONG
        )
        return {kind: rate_t_ha}

    mapping = {
        "compost": Amendment.COMPOST,
        "farmyard_manure": Amendment.FARMYARD_MANURE,
        "green_manure": Amendment.GREEN_MANURE,
    }
    if straw_management in mapping:
        return {mapping[straw_management]: rate_t_ha}

    raise ValueError(f"unrecognised straw_management: {straw_management!r}")
