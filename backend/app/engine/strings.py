"""String (series/parallel) configuration design and validation. Spec §4 Stage 6 / §5
Stage 5 (on-grid reuses the off-grid string flow verbatim). ARD §4.4 — "the money module":
this is the single most persuasive graphic in the demo (MpptWindowBar), so every number
here must be traceable to a spec clause.
"""
from __future__ import annotations

import math
from typing import Optional

from . import constants
from .types import Check, InverterSpec, ModuleSpec, StringDesign


def series_max(mppt_max_v: float, voc: float) -> int:
    """Spec §4 Stage 6. ``Series Max = FLOOR(MPPT_max x 0.85 / Voc)``. The 0.85 buffer
    accounts for cold-temperature Voc rise."""
    return math.floor(mppt_max_v * constants.COLD_VOC_BUFFER / voc)


def _voc_cold(series: int, module: ModuleSpec) -> tuple[float, str]:
    """ARD §4.4. Uses the module's temperature coefficient when known; otherwise falls
    back to the flat 0.85 buffer already baked into :func:`series_max` — in which case the
    cold-adjusted string voltage is reported equal to the nominal string voltage (the
    buffer already constrained *how many* panels may be in series, so no further per-volt
    adjustment is applied here)."""
    nominal_voc_string = series * module.voc
    coeff = module.temp_coeff_voc_pct_per_c
    if coeff is None:
        return nominal_voc_string, "flat_0.85_buffer"
    # Voc x (1 + coeff/100 x (T_cold - 25)); coeff is negative (Voc falls as temp rises),
    # so a T_cold below 25 pushes Voc up.
    adjusted = module.voc * (1 + coeff / 100 * (constants.COLD_TEMP_C - 25))
    return series * adjusted, "temp_coefficient"


def _attempt_checks(
    series: int,
    parallel: int,
    panel_count: int,
    module: ModuleSpec,
    inverter: InverterSpec,
) -> tuple[list[Check], float, float, float, float]:
    """Builds the three ARD §4.4 validation checks for one candidate series count.
    Returns (checks, vmp_string, voc_string, voc_cold_string, total_isc)."""
    vmp_string = series * module.vmp
    voc_string = series * module.voc
    total_isc = parallel * module.isc
    max_current = inverter.max_input_current_per_mppt_a * inverter.mppt_count

    vmp_pass = inverter.mppt_min_v <= vmp_string <= inverter.mppt_max_v
    vmp_margin = (
        min(
            (vmp_string - inverter.mppt_min_v) / inverter.mppt_min_v * 100
            if inverter.mppt_min_v
            else 0.0,
            (inverter.mppt_max_v - vmp_string) / inverter.mppt_max_v * 100
            if inverter.mppt_max_v
            else 0.0,
        )
        if vmp_pass
        else -abs(vmp_string - max(min(vmp_string, inverter.mppt_max_v), inverter.mppt_min_v))
    )

    voc_pass = voc_string < inverter.max_dc_voltage_v
    voc_margin = (
        (inverter.max_dc_voltage_v - voc_string) / inverter.max_dc_voltage_v * 100
        if inverter.max_dc_voltage_v
        else 0.0
    )

    isc_pass = total_isc < max_current
    isc_margin = (max_current - total_isc) / max_current * 100 if max_current else 0.0

    checks = [
        Check(
            id="vmp_in_mppt",
            label="String Vmp within MPPT window",
            expected=f"{inverter.mppt_min_v:.0f}–{inverter.mppt_max_v:.0f} V",
            actual=round(vmp_string, 1),
            unit="V",
            passed=vmp_pass,
            margin_pct=round(vmp_margin, 1),
        ),
        Check(
            id="voc_below_max_dc",
            label="String Voc below inverter max DC voltage",
            expected=f"< {inverter.max_dc_voltage_v:.0f} V",
            actual=round(voc_string, 1),
            unit="V",
            passed=voc_pass,
            margin_pct=round(voc_margin, 1),
        ),
        Check(
            id="isc_within_mppt_current",
            label="Total Isc within inverter MPPT current limit",
            expected=f"< {max_current:.1f} A",
            actual=round(total_isc, 1),
            unit="A",
            passed=isc_pass,
            margin_pct=round(isc_margin, 1),
        ),
    ]
    return checks, vmp_string, voc_string, total_isc, max_current


def design_strings(panel_count: int, module: ModuleSpec, inverter: InverterSpec) -> StringDesign:
    """Spec §4 Stage 6 / ARD §4.4. Searches series counts from ``series_max`` downward for
    the largest that satisfies all three validation checks. If none does, the *closest*
    attempt (fewest failing checks, then highest series) is returned with ``status='fail'``
    so the UI can explain why.
    """
    max_series = series_max(inverter.mppt_max_v, module.voc)
    best: Optional[tuple[int, int, list[Check]]] = None
    best_fail_count = None

    for series in range(max_series, 0, -1):
        parallel = math.ceil(panel_count / series)
        checks, *_ = _attempt_checks(series, parallel, panel_count, module, inverter)
        fail_count = sum(1 for c in checks if not c.passed)
        if fail_count == 0:
            best = (series, parallel, checks)
            best_fail_count = 0
            break
        if best_fail_count is None or fail_count < best_fail_count:
            best = (series, parallel, checks)
            best_fail_count = fail_count

    if best is None:
        # series_max was 0 (Voc alone exceeds the MPPT window) — still report a 1-series
        # attempt so the UI has something concrete to show as failing.
        series, parallel = 1, panel_count
        checks, *_ = _attempt_checks(series, parallel, panel_count, module, inverter)
        best = (series, parallel, checks)
        best_fail_count = sum(1 for c in checks if not c.passed)

    series, parallel, checks = best
    status = "pass" if best_fail_count == 0 else "fail"

    vmp_string = series * module.vmp
    voc_string = series * module.voc
    voc_cold_string, voc_method = _voc_cold(series, module)
    total_isc = parallel * module.isc
    panels_used = series * parallel
    # Orphan panels: parallel is rounded UP (CEIL), so the last string may be short a few
    # panels — that shortfall is how many field-counted panels don't fit evenly into whole
    # strings at this series count.
    remainder = panel_count % series if series else 0
    orphan_panels = 0 if remainder == 0 else (series - remainder)

    return StringDesign(
        status=status,
        series=series,
        parallel=parallel,
        config_label=f"{series}S × {parallel}P",
        panels_used=panels_used,
        orphan_panels=orphan_panels,
        vmp_string=round(vmp_string, 1),
        voc_string=round(voc_string, 1),
        voc_cold_string=round(voc_cold_string, 1),
        voc_method=voc_method,  # type: ignore[arg-type]
        total_isc=round(total_isc, 1),
        checks=tuple(checks),
    )


def validate_inverter(
    panel_count: int, module: ModuleSpec, inverter: InverterSpec
) -> StringDesign:
    """ARD §4.5 — when the manager names an inverter explicitly (demo: "standard 10kW
    Huawei string inverter"), validate the string design against *that* inverter instead of
    auto-selecting one. Identical logic to :func:`design_strings` — the "selection" step
    lives in inverter.py, not here."""
    return design_strings(panel_count, module, inverter)
