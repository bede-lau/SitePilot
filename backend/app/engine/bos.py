"""Auto-generated Balance-of-System protection spec. Spec §8. ARD §4.7.

Takes the raw ``InverterSpec`` (not the summary ``InverterSelection``) because
BOS sizing needs ``phase`` and ``has_anti_islanding``, which aren't part of the
frozen ``InverterSelection`` output contract in ``types.py``. ``report.py``
still has the raw spec in hand at this point (it's the same object handed to
``strings.design_strings``), so this costs nothing at the call site.
"""
from __future__ import annotations

from . import constants
from .types import BosGroup, BosItem, BosSpec, InverterSpec, StringDesign


def _ceil_to_standard(value: float, standard: tuple[float, ...]) -> float:
    """Smallest value in ``standard`` that is >= ``value``; the largest listed
    size if even that isn't enough (rather than raising — the report should
    still render, flagged via the item's own note)."""
    for size in standard:
        if value <= size:
            return size
    return standard[-1]


def _ac_current_a(ac_kw: float, phase: str) -> float:
    """Spec §8 cable-sizing block. ``I_ac = AC(kW) x 1000 / (V x PF)``,
    three-phase using line voltage x sqrt(3)."""
    if phase == "three":
        return ac_kw * 1000 / (constants.AC_VOLTAGE_THREE_PHASE * (3 ** 0.5) * constants.AC_POWER_FACTOR)
    return ac_kw * 1000 / (constants.AC_VOLTAGE_SINGLE_PHASE * constants.AC_POWER_FACTOR)


def _cable_for_current(min_current_a: float) -> tuple[float, float]:
    """First ``CABLE_AMPACITY`` row whose ampacity covers ``min_current_a``;
    falls back to the largest listed size."""
    for mm2, amp in constants.CABLE_AMPACITY:
        if amp >= min_current_a:
            return mm2, amp
    return constants.CABLE_AMPACITY[-1]


def generate_bos_spec(
    string_design: StringDesign, inverter: InverterSpec, system_type: str
) -> BosSpec:
    """Spec §8. ``module_isc`` (the per-panel Isc the DC fuse formula uses) is
    recovered from the string design as ``total_isc / parallel`` — exact,
    since ``total_isc`` was itself built as ``parallel × module.isc``."""
    module_isc = string_design.total_isc / string_design.parallel if string_design.parallel else 0.0

    # --- DC Protection ---
    dc_fuse_calc = constants.DC_FUSE_MARGIN * module_isc
    dc_fuse_rating = _ceil_to_standard(dc_fuse_calc, constants.DC_FUSE_STANDARD_A)

    isolator_calc = string_design.voc_string * constants.DC_ISOLATOR_MARGIN
    isolator_rating = _ceil_to_standard(isolator_calc, constants.DC_ISOLATOR_STANDARD_V)

    combiner_required = string_design.parallel > 2

    dc_items = (
        BosItem(
            item="String DC fuse",
            spec=f"{constants.DC_FUSE_MARGIN} × Isc per string",
            rating=f"{dc_fuse_rating:.0f} A gPV",
            standard="IEC 62548",
            note=f"Calculated {dc_fuse_calc:.1f} A → next standard size",
        ),
        BosItem(
            item="DC isolator",
            spec=f"System voltage × {constants.DC_ISOLATOR_MARGIN}",
            rating=f"{isolator_rating:.0f} V",
            standard="MS IEC 60947",
            note=f"Calculated {isolator_calc:.1f} V (Voc string {string_design.voc_string:.1f} V) → next standard size",
        ),
        BosItem(
            item="DC surge protection (Type 2)",
            spec="One per string combiner",
            rating="Type 2 SPD",
            standard="IEC 62548",
            note="Required on every DC combiner.",
        ),
        BosItem(
            item="DC combiner box",
            spec="Required if > 2 strings",
            rating="Required" if combiner_required else "Not required",
            standard="IEC 62548",
            note=f"{string_design.parallel} parallel string(s).",
        ),
        BosItem(
            item="Reverse-polarity protection",
            spec="Fuse or diode protection",
            rating="Required",
            standard="IEC 62548",
            note="Protects against a mis-wired string.",
        ),
    )

    # --- AC Protection ---
    ac_current = _ac_current_a(inverter.ac_rating_kw, inverter.phase)
    ac_mcb_rating = _ceil_to_standard(ac_current, constants.AC_MCB_STANDARD_A)

    ac_items = (
        BosItem(
            item="AC MCB",
            spec="Rated for inverter AC output current",
            rating=f"{ac_mcb_rating:.0f} A",
            standard="MS IEC 60947",
            note=f"Calculated {ac_current:.1f} A ({inverter.phase}-phase) → next standard size",
        ),
        BosItem(
            item="AC surge protection (Type 2)",
            spec="Required at the distribution board",
            rating="Type 2 SPD",
            standard="IEC 62548",
            note="Required.",
        ),
        BosItem(
            item="RCCB / ELCB",
            spec="30 mA sensitivity",
            rating="30 mA",
            standard="IEC 60364",
            note="Required.",
        ),
        BosItem(
            item="Over/under-voltage protection",
            spec="Built into inverter",
            rating="Verify in datasheet",
            standard="TNB TCG",
            note="Confirm against the inverter's spec sheet.",
        ),
        BosItem(
            item="Anti-islanding protection",
            spec="Built into grid-tie / hybrid inverter",
            rating="Required",
            standard="TNB TCG",
            note="Present per catalog spec." if inverter.has_anti_islanding else "NOT present on this inverter — do not connect to TNB grid.",
        ),
    )

    # --- Earthing ---
    earthing_items = (
        BosItem(
            item="DC earthing",
            spec="Separate from AC earthing",
            rating="Separate DC earth",
            standard="IEC 60364",
            note="Do not bond DC and AC earths.",
        ),
        BosItem(
            item="AC earthing",
            spec="Separate from DC earthing",
            rating="Separate AC earth",
            standard="IEC 60364",
            note="Do not bond DC and AC earths.",
        ),
        BosItem(
            item="Copper earth rod",
            spec=f"≥ {constants.EARTH_ROD_MIN_DIAMETER_MM:.0f} mm diameter, {constants.EARTH_ROD_LENGTH_M} m length",
            rating=f"{constants.EARTH_ROD_MIN_DIAMETER_MM:.0f} mm × {constants.EARTH_ROD_LENGTH_M} m Cu rod",
            standard="IEC 60364",
            note="Standard copper earth rod.",
        ),
        BosItem(
            item="Earth resistance",
            spec=f"≤ {constants.EARTH_RESISTANCE_MAX_OHM} Ω",
            rating=f"≤ {constants.EARTH_RESISTANCE_MAX_OHM} Ω",
            standard="IEC 60364",
            note="Test and record at commissioning.",
        ),
    )

    # --- Cables ---
    ac_cable_target = ac_current * constants.AC_CURRENT_MARGIN
    ac_cable_mm2, ac_cable_amp = _cable_for_current(ac_cable_target)

    cable_items = [
        BosItem(
            item="DC PV cable (panel to combiner)",
            spec=f"Isc per string ({module_isc:.1f} A), ≤ 15 m run",
            rating=f"{constants.DC_STRING_CABLE_MM2:.0f} mm²",
            standard="IEC 62548",
            note=f"Voltage drop budget ≤ {constants.VOLTAGE_DROP_BUDGET_PCT}%.",
        ),
    ]
    if system_type == "hybrid":
        cable_items.append(
            BosItem(
                item="DC battery cable (battery to inverter)",
                spec="Inverter max charge/discharge current, ≤ 2 m run",
                rating=f"{constants.DC_BATTERY_CABLE_MM2:.0f} mm²",
                standard="IEC 62548",
                note=f"Voltage drop budget ≤ {constants.VOLTAGE_DROP_BUDGET_PCT}%.",
            )
        )
    cable_items.append(
        BosItem(
            item="AC cable (inverter to distribution board)",
            spec=f"I_ac × {constants.AC_CURRENT_MARGIN} = {ac_cable_target:.1f} A",
            rating=f"{ac_cable_mm2:.0f} mm² ({ac_cable_amp:.0f} A ampacity)",
            standard="IEC 60364",
            note=f"Voltage drop budget ≤ {constants.VOLTAGE_DROP_BUDGET_PCT}%.",
        )
    )

    return BosSpec(
        groups=(
            BosGroup(group="DC Protection", items=dc_items),
            BosGroup(group="AC Protection", items=ac_items),
            BosGroup(group="Earthing", items=earthing_items),
            BosGroup(group="Cables", items=tuple(cable_items)),
        )
    )
