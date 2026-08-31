"""Roof & site assessment. Spec §4 Stage 2."""
from __future__ import annotations

import math
from typing import Optional

from . import constants
from .types import EfficiencyBreakdown, Flag, Obstruction


def _tilt_factor(tilt_deg: float) -> float:
    """Spec §4 Stage 2D tilt-factor band."""
    for upper, factor in constants.TILT_FACTORS:
        if tilt_deg <= upper:
            return factor
    return constants.TILT_FACTORS[-1][1]


def _azimuth_factor(azimuth_deg: float) -> float:
    """Spec §4 Stage 2D azimuth-factor band (degrees from true south, 0 = south)."""
    magnitude = abs(azimuth_deg)
    for upper, factor in constants.AZIMUTH_FACTORS:
        if magnitude <= upper:
            return factor
    return constants.AZIMUTH_FACTOR_BEYOND_90


def azimuth_flag(azimuth_deg: Optional[float]) -> Optional[Flag]:
    """Spec §4 Stage 2D: '>90° — suboptimal, warn user'. Does not raise (ARD: never raise
    on a soft problem)."""
    if azimuth_deg is not None and abs(azimuth_deg) > 90:
        return Flag(
            level="warn",
            code="AZIMUTH_SUBOPTIMAL",
            message=(
                f"Roof azimuth {azimuth_deg:.0f}° from south is beyond the 90° "
                "band the efficiency table covers — orientation is suboptimal."
            ),
        )
    return None


def effective_efficiency(
    tilt_deg: Optional[float],
    azimuth_deg: Optional[float],
    shading_factor: Optional[float],
) -> EfficiencyBreakdown:
    """Spec §4 Stage 2D. ``Effective Efficiency = 0.75 x Tilt x Azimuth x Shading x 0.85``.

    Null inputs fall back to the Project column defaults (ARD §3.1): 15° tilt, 0° azimuth
    (true south), 0.95 shading.
    """
    tilt = constants.DEFAULT_ROOF_TILT_DEG if tilt_deg is None else tilt_deg
    azimuth = constants.DEFAULT_ROOF_AZIMUTH_DEG if azimuth_deg is None else azimuth_deg
    shading = constants.DEFAULT_SHADING_FACTOR if shading_factor is None else shading_factor

    tilt_f = _tilt_factor(tilt)
    azimuth_f = _azimuth_factor(azimuth)
    effective = constants.BASE_EFFICIENCY * tilt_f * azimuth_f * shading * constants.TEMP_DERATING

    return EfficiencyBreakdown(
        base=constants.BASE_EFFICIENCY,
        tilt=tilt_f,
        azimuth=azimuth_f,
        shading=shading,
        temperature=constants.TEMP_DERATING,
        effective=effective,
    )


def net_usable_area(roof_area_m2: Optional[float], obstructions: tuple[Obstruction, ...]) -> Optional[float]:
    """Spec §4 Stage 2B. Returns ``None`` when the roof area itself is unknown (the caller
    then skips the roof-constraint branch of array sizing entirely)."""
    if roof_area_m2 is None:
        return None
    deduction = sum(
        constants.OBSTRUCTION_AREA_M2.get(o.kind, 0.0) * o.count for o in obstructions
    )
    return max(0.0, roof_area_m2 - deduction)


def max_panels_from_roof(net_area_m2: Optional[float]) -> Optional[int]:
    """Spec §4 Stage 2C. ``Max Panels = FLOOR(Net Usable Area / 2.1)``."""
    if net_area_m2 is None:
        return None
    return math.floor(net_area_m2 / constants.PANEL_FOOTPRINT_M2)
