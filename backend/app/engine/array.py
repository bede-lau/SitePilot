"""Load calculation + PV array sizing. Spec §5 Stages 1 & 3 (on-grid/hybrid share this
flow — off-grid is out of scope, ARD D5). ARD §4.3.
"""
from __future__ import annotations

import math
from typing import Optional

from . import constants
from .types import ArraySizing, Flag, ModuleSpec, ModuleSummary


def design_daily_wh(monthly_kwh: float) -> float:
    """Spec §5 Stage 1. ``Design Daily (Wh) = (Monthly kWh / 30) x 1000 x 1.2``."""
    daily_kwh = monthly_kwh / 30
    return daily_kwh * 1000 * constants.SAFETY_FACTOR_LOAD


def required_array_kwp(design_daily_wh_: float, psh: float, eff: float) -> float:
    """Spec §5 Stage 3A. ``Required Array (kWp) = Design Daily (Wh) / (PSH x Eff x 1000)``."""
    return design_daily_wh_ / (psh * eff * 1000)


def _module_summary(module: ModuleSpec) -> ModuleSummary:
    return ModuleSummary(
        manufacturer=module.manufacturer,
        model=module.model,
        rated_wp=module.rated_wp,
        vmp=module.vmp,
        voc=module.voc,
        imp=module.imp,
        isc=module.isc,
        bnef_tier1=module.bnef_tier1,
    )


def _self_consumption(
    panel_count: int,
    module_wp: float,
    psh: float,
    eff: float,
    design_daily_wh_: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float], list[Flag]]:
    """Spec §5 Stage 3C. Compares daily generation against the safety-factor-inflated
    design load (the same "design daily" figure Stage 1 produced) — not the raw bill kWh.
    Returns (daily_generation_kwh, self_consumed_kwh, exported_kwh, self_consumption_pct, flags).
    """
    actual_kwp = panel_count * module_wp / 1000
    daily_generation_kwh = actual_kwp * psh * eff
    if design_daily_wh_ is None:
        return daily_generation_kwh, None, None, None, []

    design_daily_kwh = design_daily_wh_ / 1000
    self_consumed_kwh = min(daily_generation_kwh, design_daily_kwh)
    exported_kwh = max(0.0, daily_generation_kwh - design_daily_kwh)
    self_consumption_pct = (
        (self_consumed_kwh / daily_generation_kwh * 100) if daily_generation_kwh > 0 else 0.0
    )

    flags: list[Flag] = []
    if daily_generation_kwh > 0 and (exported_kwh / daily_generation_kwh) > 0.30:
        flags.append(
            Flag(
                level="warn",
                code="OVERSIZED",
                message=(
                    "System may be oversized: exported energy earns only the Solar ATAP "
                    "SMP rate versus the higher self-consumed savings rate. Consider "
                    "reducing array size."
                ),
            )
        )
    return daily_generation_kwh, self_consumed_kwh, exported_kwh, self_consumption_pct, flags


def size_array(
    design_daily_wh_: Optional[float],
    psh: float,
    eff: float,
    max_roof_kwp: Optional[float],
    module: ModuleSpec,
) -> tuple[ArraySizing, list[Flag]]:
    """Spec §5 Stages 3A-3D — consumption-driven sizing path.

    When ``design_daily_wh_`` is ``None`` (no consumption on record and no explicit panel
    count either) this cannot size anything; callers should prefer
    :func:`array_from_panel_count` whenever a field panel count is available (ARD §4.3 —
    "the field CV count is authoritative").
    """
    flags: list[Flag] = []
    if design_daily_wh_ is None:
        raise ValueError(
            "size_array requires design_daily_wh_ (a monthly_consumption_kwh); "
            "use array_from_panel_count for the CV-count-driven path"
        )

    required_kwp = required_array_kwp(design_daily_wh_, psh, eff)

    if max_roof_kwp is not None and required_kwp > max_roof_kwp:
        constrained = True
        coverage_pct = (max_roof_kwp / required_kwp * 100) if required_kwp > 0 else 0.0
        final_kwp = max_roof_kwp
        flags.append(
            Flag(
                level="warn",
                code="ROOF_CONSTRAINED",
                message=(
                    f"Roof supports {max_roof_kwp:.2f} kWp — covers {coverage_pct:.0f}% "
                    "of load. Remaining load still sourced from the grid."
                ),
            )
        )
    else:
        constrained = False
        coverage_pct = 100.0
        final_kwp = required_kwp * constants.SIZING_MARGIN

    panel_count = math.ceil(final_kwp * 1000 / module.rated_wp)
    actual_kwp = panel_count * module.rated_wp / 1000

    daily_gen, self_consumed, exported, self_pct, sc_flags = _self_consumption(
        panel_count, module.rated_wp, psh, eff, design_daily_wh_
    )
    flags.extend(sc_flags)

    sizing = ArraySizing(
        panel_count=panel_count,
        module=_module_summary(module),
        actual_kwp=round(actual_kwp, 3),
        required_kwp=round(required_kwp, 3),
        max_roof_kwp=round(max_roof_kwp, 3) if max_roof_kwp is not None else None,
        constrained=constrained,
        coverage_pct=round(coverage_pct, 1) if coverage_pct is not None else None,
        daily_generation_kwh=round(daily_gen, 3) if daily_gen is not None else None,
        self_consumed_kwh=round(self_consumed, 3) if self_consumed is not None else None,
        exported_kwh=round(exported, 3) if exported is not None else None,
        self_consumption_pct=round(self_pct, 1) if self_pct is not None else None,
    )
    return sizing, flags


def array_from_panel_count(
    panel_count: int,
    module: ModuleSpec,
    psh: float,
    eff: float,
    design_daily_wh_: Optional[float] = None,
    max_roof_kwp: Optional[float] = None,
) -> tuple[ArraySizing, list[Flag]]:
    """ARD §4.3 EPC entry point — the field CV panel count is authoritative, so this skips
    load-driven sizing. ``required_kwp`` is reported as ``None`` (nothing was "required" —
    the count is a fact from the field, not a target)."""
    flags: list[Flag] = []
    actual_kwp = panel_count * module.rated_wp / 1000

    constrained = False
    coverage_pct: Optional[float] = None
    if max_roof_kwp is not None and actual_kwp > max_roof_kwp:
        constrained = True
        coverage_pct = (max_roof_kwp / actual_kwp * 100) if actual_kwp > 0 else 0.0
        flags.append(
            Flag(
                level="warn",
                code="PANEL_COUNT_EXCEEDS_ROOF",
                message=(
                    f"{panel_count} panels ({actual_kwp:.2f} kWp) exceed the roof's "
                    f"estimated {max_roof_kwp:.2f} kWp capacity — verify the field count "
                    "and roof measurement."
                ),
            )
        )

    daily_gen, self_consumed, exported, self_pct, sc_flags = _self_consumption(
        panel_count, module.rated_wp, psh, eff, design_daily_wh_
    )
    flags.extend(sc_flags)

    sizing = ArraySizing(
        panel_count=panel_count,
        module=_module_summary(module),
        actual_kwp=round(actual_kwp, 3),
        required_kwp=None,
        max_roof_kwp=round(max_roof_kwp, 3) if max_roof_kwp is not None else None,
        constrained=constrained,
        coverage_pct=round(coverage_pct, 1) if coverage_pct is not None else None,
        daily_generation_kwh=round(daily_gen, 3) if daily_gen is not None else None,
        self_consumed_kwh=round(self_consumed, 3) if self_consumed is not None else None,
        exported_kwh=round(exported, 3) if exported is not None else None,
        self_consumption_pct=round(self_pct, 1) if self_pct is not None else None,
    )
    return sizing, flags
