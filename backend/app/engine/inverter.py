"""Inverter selection & validation. Spec §5 Stage 4. ARD §4.5.

Deviates from the ARD's stated signatures in one respect: ``select_inverter``
returns the chosen ``InverterSpec`` *alongside* the summary ``InverterSelection``
(``tuple[InverterSpec, InverterSelection]``), because ``types.InverterSelection``
(the frozen output contract in ``types.py``) doesn't carry the fields
(``max_input_current_per_mppt_a``, ``mppt_count``, ``phase``) that
``strings.design_strings`` needs afterwards — ``report.py`` has to hand the
*raw* chosen spec on to string design, not just the summary. ``validate_inverter``
here only needs ``(array_kwp, inverter)`` since the caller already holds the
``InverterSpec`` in that case.
"""
from __future__ import annotations

from . import constants
from .types import Check, InverterSelection, InverterSpec


def target_ac_kw(array_kwp: float, ratio: float = constants.DCAC_RATIO_DEFAULT) -> float:
    """Spec §5 Stage 4A. ``Target AC (kW) = Array kWp / ratio``."""
    return array_kwp / ratio if ratio else 0.0


def dc_ac_ratio(array_kwp: float, ac_kw: float) -> float:
    return array_kwp / ac_kw if ac_kw else 0.0


def _checks(array_kwp: float, inverter: InverterSpec, ratio: float) -> list[Check]:
    """The three ARD §4.5 validation rows. The DC:AC band check uses the
    official [1.2, 1.5] band (constants.DCAC_RATIO_MIN/MAX) for transparency
    — it may show ``passed=False`` for a manager-specified inverter (e.g. the
    PRD §6 demo's 20-panel / 10 kW Huawei pairing lands at 1.1x, just under
    the 1.2x floor) without that alone failing the whole report; see
    ``report.py``'s status aggregation for why."""
    ratio_pass = constants.DCAC_RATIO_MIN <= ratio <= constants.DCAC_RATIO_MAX
    dc_input_pass = inverter.max_dc_input_kw >= array_kwp

    return [
        Check(
            id="dc_ac_ratio_band",
            label="DC:AC ratio within recommended band",
            expected=f"{constants.DCAC_RATIO_MIN}–{constants.DCAC_RATIO_MAX}",
            actual=round(ratio, 3),
            unit="ratio",
            passed=ratio_pass,
            margin_pct=None,
        ),
        Check(
            id="max_dc_input_kw",
            label="Inverter max DC input covers array size",
            expected=f">= {array_kwp:.2f} kWp",
            actual=inverter.max_dc_input_kw,
            unit="kWp",
            passed=dc_input_pass,
            margin_pct=(
                round((inverter.max_dc_input_kw - array_kwp) / array_kwp * 100, 1)
                if array_kwp
                else None
            ),
        ),
        Check(
            id="anti_islanding",
            label="Anti-islanding protection present",
            expected="present",
            actual=1.0 if inverter.has_anti_islanding else 0.0,
            unit="bool",
            passed=inverter.has_anti_islanding,
            margin_pct=None,
        ),
    ]


def _to_selection(
    inverter: InverterSpec, array_kwp: float, selected_by: str
) -> InverterSelection:
    ratio = dc_ac_ratio(array_kwp, inverter.ac_rating_kw)
    checks = _checks(array_kwp, inverter, ratio)
    return InverterSelection(
        manufacturer=inverter.manufacturer,
        model=inverter.model,
        ac_rating_kw=inverter.ac_rating_kw,
        max_dc_input_kw=inverter.max_dc_input_kw,
        mppt_min_v=inverter.mppt_min_v,
        mppt_max_v=inverter.mppt_max_v,
        max_dc_voltage_v=inverter.max_dc_voltage_v,
        dc_ac_ratio=round(ratio, 3),
        selected_by=selected_by,  # type: ignore[arg-type]
        checks=tuple(checks),
    )


def select_inverter(
    array_kwp: float,
    catalog: tuple[InverterSpec, ...],
    tier: str,
    system_type: str,
    target_ratio: float = constants.DCAC_RATIO_DEFAULT,
) -> tuple[InverterSpec, InverterSelection]:
    """Spec §5 Stage 4. Smallest catalog inverter whose ``ac_rating_kw`` covers
    the target AC rating and whose ``max_dc_input_kw`` covers the array, with a
    preference for the budget tier's brand list (ARD §4.1 ``EQUIPMENT_BY_TIER``).
    Falls back progressively (drop the ratio-band preference, then take the
    largest available) rather than raising, so a thin catalog still produces
    *something* the UI can show with its checks visible. ``target_ratio`` is
    ``DesignInputs.dc_ac_ratio_target`` threaded through by ``report.py``.
    """
    if not catalog:
        raise ValueError("select_inverter: catalog is empty — nothing to select from")

    target = target_ac_kw(array_kwp, target_ratio)
    tier_key = "inverter_hybrid" if system_type == "hybrid" else "inverter_on_grid"
    preferred_brands = tuple(
        b.lower() for b in constants.EQUIPMENT_BY_TIER.get(tier_key, {}).get(tier, ())
    )

    def brand_rank(inv: InverterSpec) -> int:
        name = inv.manufacturer.lower()
        return 0 if any(b in name or name in b for b in preferred_brands) else 1

    def in_band(inv: InverterSpec) -> bool:
        ratio = dc_ac_ratio(array_kwp, inv.ac_rating_kw)
        return constants.DCAC_RATIO_MIN <= ratio <= constants.DCAC_RATIO_MAX

    capacity_ok = [
        inv
        for inv in catalog
        if inv.ac_rating_kw >= target and inv.max_dc_input_kw >= array_kwp
    ]
    candidates = [inv for inv in capacity_ok if in_band(inv)] or capacity_ok or list(catalog)

    candidates.sort(key=lambda inv: (brand_rank(inv), inv.ac_rating_kw))
    chosen = candidates[0]
    return chosen, _to_selection(chosen, array_kwp, "auto")


def validate_inverter(array_kwp: float, inverter: InverterSpec) -> InverterSelection:
    """ARD §4.5 — when the manager names an inverter explicitly (demo: "standard
    10kW Huawei string inverter"), validate that one instead of auto-selecting."""
    return _to_selection(inverter, array_kwp, "user")
