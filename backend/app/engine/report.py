"""Single entry point orchestrating §4.2 → §4.9 in the spec §10 report order.
ARD §4.10. This is the only function ``agents/tools.py`` / ``services/feasibility_engine.py``
calls into the engine through.
"""
from __future__ import annotations

from . import array as array_mod
from . import battery as battery_mod
from . import bos as bos_mod
from . import confidence as confidence_mod
from . import constants
from . import financial as financial_mod
from . import inverter as inverter_mod
from . import site as site_mod
from . import strings as strings_mod
from .battery import UnsupportedSystemType
from .types import (
    ConfidenceSignals,
    DesignInputs,
    DesignReport,
    Flag,
    LoadProfile,
    SiteAssessment,
)

# A hybrid system with no critical appliances selected still needs *something*
# to size the battery against — default to the spec §6 Stage 4A worked
# example's own minimal set (fridge + lights + router + fans) rather than
# producing a degenerate zero-capacity battery. Documented in `assumptions`.
_DEFAULT_CRITICAL_APPLIANCES: tuple[str, ...] = ("refrigerator", "lights", "wifi_router", "fans")

# Checks whose failure represents a genuine engineering/safety problem, not
# just a soft "outside the ideal design band" advisory — see inverter.py's
# docstring on the DC:AC ratio check for why that one doesn't gate `status`.
_CRITICAL_INVERTER_CHECK_IDS = frozenset({"max_dc_input_kw", "anti_islanding"})

# Warning codes that represent a genuine degradation of the design (the
# array can't cover the target load, or the roof orientation itself is
# suboptimal) vs. purely informational advisories. ARD §5.3's own worked
# example shows `"status": "pass"` *with* an ORPHAN_PANELS warning present
# simultaneously — confirming warnings don't automatically downgrade status;
# only this curated subset does. DCAC_RATIO_OUT_OF_BAND and ORPHAN_PANELS are
# deliberately excluded: a user-specified inverter that's comfortably (not
# dangerously) oversized, or a string layout with a few unused panel slots,
# is worth surfacing but isn't a "the recommendation is degraded" condition.
_STATUS_DOWNGRADING_CODES = frozenset({"ROOF_CONSTRAINED", "PANEL_COUNT_EXCEEDS_ROOF", "AZIMUTH_SUBOPTIMAL"})


def run_design(inputs: DesignInputs) -> DesignReport:
    if inputs.system_type == "off_grid":
        raise UnsupportedSystemType(
            "Off-grid systems are out of scope for this engine (ARD D5) — "
            "only on_grid and hybrid are supported."
        )

    warnings: list[Flag] = []
    assumptions: list[str] = []

    # --- Stage 2: site & efficiency --------------------------------------
    eff = site_mod.effective_efficiency(inputs.roof_tilt_deg, inputs.roof_azimuth_deg, inputs.shading_factor)
    az_flag = site_mod.azimuth_flag(inputs.roof_azimuth_deg)
    if az_flag is not None:
        warnings.append(az_flag)

    net_area = site_mod.net_usable_area(inputs.roof_area_m2, inputs.obstructions)
    max_panels = site_mod.max_panels_from_roof(net_area)
    psh, psh_is_fallback = constants.psh_for_state(inputs.state)
    max_roof_kwp = round(max_panels * inputs.module.rated_wp / 1000, 3) if max_panels is not None else None

    if inputs.roof_tilt_deg is None:
        assumptions.append(f"Roof tilt defaulted to {constants.DEFAULT_ROOF_TILT_DEG:.0f}° (not provided).")
    if inputs.roof_azimuth_deg is None:
        assumptions.append(f"Roof azimuth defaulted to {constants.DEFAULT_ROOF_AZIMUTH_DEG:.0f}° / true south (not provided).")
    if inputs.shading_factor is None:
        assumptions.append(f"Shading factor defaulted to {constants.DEFAULT_SHADING_FACTOR} (not provided).")
    assumptions.append(f"Temperature derating {constants.TEMP_DERATING} fixed for Malaysian ambient conditions.")
    if psh_is_fallback:
        assumptions.append(
            f"'{inputs.state}' was not recognised — PSH defaulted to the "
            f"{constants.DEFAULT_PSH_STATE} state average ({psh} hrs/day)."
        )
    else:
        assumptions.append(
            f"PSH is the {inputs.state} state average ({psh} hrs/day) — no "
            "per-address irradiance API is used by this product."
        )

    site = SiteAssessment(
        state=inputs.state,
        psh=psh,
        psh_source="state_default_fallback" if psh_is_fallback else "state_average",
        roof_area_m2=inputs.roof_area_m2,
        net_area_m2=round(net_area, 3) if net_area is not None else None,
        max_panels=max_panels,
        efficiency=eff,
    )

    # --- Stage 1/3: load + array sizing -----------------------------------
    design_daily_wh_ = (
        array_mod.design_daily_wh(inputs.monthly_consumption_kwh)
        if inputs.monthly_consumption_kwh is not None
        else None
    )
    load = LoadProfile(
        monthly_kwh=inputs.monthly_consumption_kwh,
        daily_kwh=round(inputs.monthly_consumption_kwh / 30, 3) if inputs.monthly_consumption_kwh is not None else None,
        design_daily_wh=round(design_daily_wh_, 1) if design_daily_wh_ is not None else None,
        safety_factor=constants.SAFETY_FACTOR_LOAD,
    )

    if inputs.panel_count is not None:
        # ARD §4.3 EPC entry point — the field CV count is authoritative.
        sizing, arr_flags = array_mod.array_from_panel_count(
            inputs.panel_count, inputs.module, psh, eff.effective, design_daily_wh_, max_roof_kwp
        )
    elif inputs.monthly_consumption_kwh is not None:
        sizing, arr_flags = array_mod.size_array(design_daily_wh_, psh, eff.effective, max_roof_kwp, inputs.module)
    else:
        raise ValueError(
            "run_design requires either panel_count (field CV count) or "
            "monthly_consumption_kwh (bill-driven sizing) — DesignInputs had neither."
        )
    warnings.extend(arr_flags)

    # --- Stage 4: inverter selection / validation --------------------------
    if inputs.inverter is not None:
        inverter_spec_used = inputs.inverter
        inverter_selection = inverter_mod.validate_inverter(sizing.actual_kwp, inputs.inverter)
    elif inputs.inverter_catalog:
        inverter_spec_used, inverter_selection = inverter_mod.select_inverter(
            sizing.actual_kwp,
            inputs.inverter_catalog,
            inputs.budget_tier,
            inputs.system_type,
            inputs.dc_ac_ratio_target,
        )
    else:
        raise ValueError(
            "run_design requires either an explicit inverter or a non-empty "
            "inverter_catalog to auto-select from."
        )

    ratio_check = next((c for c in inverter_selection.checks if c.id == "dc_ac_ratio_band"), None)
    if ratio_check is not None and not ratio_check.passed:
        warnings.append(
            Flag(
                level="warn",
                code="DCAC_RATIO_OUT_OF_BAND",
                message=(
                    f"DC:AC ratio {inverter_selection.dc_ac_ratio:.2f} is outside the "
                    f"recommended {constants.DCAC_RATIO_MIN}–{constants.DCAC_RATIO_MAX} band — "
                    "not unsafe, but outside the ideal design range for this inverter pairing."
                ),
            )
        )

    # --- Stage 6: string design ---------------------------------------------
    string_design = strings_mod.design_strings(sizing.panel_count, inputs.module, inverter_spec_used)
    if string_design.status == "fail":
        warnings.append(
            Flag(
                level="error",
                code="STRING_DESIGN_FAILED",
                message="No series/parallel configuration satisfies every string validation check — see the check matrix.",
            )
        )
    if string_design.orphan_panels:
        warnings.append(
            Flag(
                level="warn",
                code="ORPHAN_PANELS",
                message=(
                    f"{string_design.orphan_panels} panel slot(s) unallocated at "
                    f"{string_design.series}S — consider a different string count or an extra MPPT."
                ),
            )
        )
    if string_design.voc_method == "flat_0.85_buffer":
        assumptions.append("Cold Voc estimated via the flat 0.85 buffer — module temperature coefficient not on record.")

    # --- Stage 6 (hybrid): battery -----------------------------------------
    battery_design = None
    if inputs.system_type == "hybrid":
        appliances = inputs.critical_appliances or _DEFAULT_CRITICAL_APPLIANCES
        if not inputs.critical_appliances:
            assumptions.append(
                "No critical appliances specified — defaulted to refrigerator + lights + WiFi router + fans."
            )
        critical_load_kw = sum(constants.CRITICAL_APPLIANCE_W.get(a, 0.0) for a in appliances) / 1000

        backup_hours = inputs.backup_hours
        if backup_hours is None:
            backup_hours = constants.BACKUP_HOURS_BY_FREQUENCY["rarely"]
            assumptions.append(f"Backup hours not specified — defaulted to {backup_hours:.0f} hrs (outage 'rarely').")

        battery_design = battery_mod.size_hybrid_battery(critical_load_kw, backup_hours)

    # --- Stage 8: BOS protection spec ---------------------------------------
    bos_spec = bos_mod.generate_bos_spec(string_design, inverter_spec_used, inputs.system_type)

    # --- Stage 9: confidence -------------------------------------------------
    signals = ConfidenceSignals(
        supplier_quote_attached=inputs.has_supplier_quote,
        string_validated_pass=(string_design.status == "pass"),
        site_specifics_recorded=any(
            v is not None for v in (inputs.roof_tilt_deg, inputs.roof_azimuth_deg, inputs.shading_factor)
        ),
        real_consumption_on_record=inputs.monthly_consumption_kwh is not None,
        manual_panel_count=(inputs.panel_count_source == "manual"),
        psh_is_fallback=psh_is_fallback,
    )
    confidence = confidence_mod.score_confidence(signals)

    # --- Stage 6/8: financial --------------------------------------------
    financial = financial_mod.run_financials(
        sizing.actual_kwp,
        psh,
        eff.effective,
        inputs.monthly_consumption_kwh,
        inputs.system_cost_myr,
        inputs.budget_tier,
        inputs.system_type,
        inputs.tariff_category,
    )
    assumptions.extend(financial.assumptions)

    # --- status aggregation -------------------------------------------------
    critical_failed = any(
        not c.passed for c in inverter_selection.checks if c.id in _CRITICAL_INVERTER_CHECK_IDS
    )
    if string_design.status == "fail" or critical_failed:
        status = "fail"
    elif any(f.code in _STATUS_DOWNGRADING_CODES for f in warnings):
        status = "warn"
    else:
        status = "pass"

    return DesignReport(
        id=None,
        project_id=inputs.project_id,
        system_type=inputs.system_type,
        status=status,  # type: ignore[arg-type]
        generated_at=inputs.generated_at,
        confidence=confidence,
        site=site,
        load=load,
        array=sizing,
        strings=string_design,
        inverter=inverter_selection,
        battery=battery_design,
        bos=bos_spec,
        financial=financial,
        equipment_tier=inputs.budget_tier,
        warnings=tuple(warnings),
        assumptions=tuple(assumptions),
    )
