"""``run_design`` — the single engine entry point. ARD §4.10 / §4.11 "PRD demo
case" row.

The PRD §6 demo case (20 panels, Longi Hi-MO7 550W, Huawei SUN2000-10KTL-M1,
Selangor) is asserted here using the values the engine *actually computes*,
not the PRD narrative's illustrative "3S x 5P / 124.5V / 148.8V" figures —
see ``test_engine_strings.py``'s module docstring for the full explanation:
a 120-500V MPPT window (required for this exact Huawei model) makes the
already-built series-selection algorithm choose series_max (8) rather than a
hand-picked 3, for any panel count, because every validation check gets
*easier*, not harder, at a higher series count. This is a real,
pre-existing spec/algorithm discrepancy, not a bug in this test suite —
flagged in the phase checkpoint. What *does* hold, and is asserted below
exactly as ARD §4.11 lists it: overall status "pass", DC:AC ratio within
[1.0, 1.5], confidence within [90, 94], and the BOS string fuse at 20A
(17.5A calculated -> next standard size) — none of those four depend on
which series count wins.
"""
import pytest

from app.engine.battery import UnsupportedSystemType
from app.engine.report import run_design
from app.engine.types import DesignInputs, InverterSpec, ModuleSpec

LONGI_550 = ModuleSpec(
    manufacturer="Longi", model="Hi-MO7 LR5-72HTH-550M",
    rated_wp=550, vmp=41.5, voc=49.6, imp=13.2, isc=14.0,
    temp_coeff_voc_pct_per_c=None, bnef_tier1=True,
)
HUAWEI_10KW = InverterSpec(
    manufacturer="Huawei", model="SUN2000-10KTL-M1", ac_rating_kw=10, max_dc_input_kw=13,
    mppt_min_v=120, mppt_max_v=500, max_dc_voltage_v=1080,
    max_input_current_per_mppt_a=26, mppt_count=2, phase="three", has_anti_islanding=True,
)


def _demo_inputs(**overrides) -> DesignInputs:
    base = dict(
        generated_at="2026-08-31T00:00:00Z",
        module=LONGI_550,
        system_type="on_grid",
        panel_count=20,
        panel_count_source="photo",
        inverter=HUAWEI_10KW,
        state="Selangor",
        has_supplier_quote=True,
    )
    base.update(overrides)
    return DesignInputs(**base)


def test_prd_demo_case():
    report = run_design(_demo_inputs())

    assert report.status == "pass"
    assert report.array.actual_kwp == pytest.approx(11.0)

    # Documented deviation from the PRD narrative — see module docstring.
    assert report.strings.status == "pass"
    assert report.strings.series == 8
    assert report.strings.config_label == "8S × 3P"

    assert 1.0 <= report.inverter.dc_ac_ratio <= 1.5

    assert 90 <= report.confidence.score <= 94
    assert report.confidence.score <= 94  # hard cap, restated explicitly

    fuse_item = next(
        i for g in report.bos.groups if g.group == "DC Protection" for i in g.items if i.item == "String DC fuse"
    )
    assert fuse_item.rating == "20 A gPV"

    assert report.battery is None  # on-grid


def test_confidence_never_exceeds_94_for_any_reasonable_input_combination():
    """ARD §4.11: no input combination can push confidence.score above 94."""
    for quote in (True, False):
        for source in ("photo", "manual"):
            for state in ("Selangor", "Nowhere"):
                for monthly_kwh in (None, 500.0):
                    for tilt in (None, 20.0):
                        report = run_design(
                            _demo_inputs(
                                has_supplier_quote=quote,
                                panel_count_source=source,
                                state=state,
                                monthly_consumption_kwh=monthly_kwh,
                                roof_tilt_deg=tilt,
                            )
                        )
                        assert report.confidence.score <= 94


def test_off_grid_raises_unsupported_system_type():
    with pytest.raises(UnsupportedSystemType):
        run_design(_demo_inputs(system_type="off_grid"))


def test_requires_panel_count_or_monthly_consumption():
    with pytest.raises(ValueError):
        run_design(_demo_inputs(panel_count=None, monthly_consumption_kwh=None))


def test_requires_inverter_or_catalog():
    with pytest.raises(ValueError):
        run_design(_demo_inputs(inverter=None, inverter_catalog=()))


def test_consumption_driven_sizing_path():
    """No panel_count given -> falls back to bill-driven sizing (spec §5
    Stage 3 worked example: 363 kWh/mo -> 11 panels, 6.05 kWp — using the
    spec's own PSH of 4.5 for that isolated formula illustration).

    This test uses PSH 4.35, not the spec's 4.5: ``constants.psh_for_state``
    (already-built, outside this agent's changes) always returns the
    Selangor *midpoint* of its (4.2, 4.5) range, and the spec's own §3.2
    table separately says "use 4.3 as default" for Selangor — three
    different Selangor PSH figures appear across the spec/ARD (4.3 default,
    4.5 in this one formula walkthrough, 4.35 midpoint as coded). Per the
    ARD's "follow the FORMULA" instruction, this asserts what
    ``constants.psh_for_state("Selangor")`` + the sizing formula actually
    produce (12 panels, ~6.6 kWp), not the spec passage's 11/6.05."""
    report = run_design(
        _demo_inputs(
            panel_count=None,
            panel_count_source="manual",
            monthly_consumption_kwh=363,
            roof_area_m2=42,
            roof_tilt_deg=15,
            roof_azimuth_deg=10,
            shading_factor=0.95,
        )
    )
    assert report.site.efficiency.effective == pytest.approx(0.593, rel=0.02)
    assert report.array.panel_count == 12
    assert report.array.actual_kwp == pytest.approx(6.6, rel=0.02)
    assert report.array.required_kwp is not None


def test_hybrid_system_produces_battery_design():
    report = run_design(
        _demo_inputs(
            system_type="hybrid",
            backup_hours=6,
            critical_appliances=("refrigerator", "lights", "wifi_router", "fans"),
        )
    )
    assert report.battery is not None
    assert report.battery.final_kwh > 0
    # Hybrid BOS spec must include the DC battery cable item.
    cable_group = next(g for g in report.bos.groups if g.group == "Cables")
    assert any(i.item.startswith("DC battery cable") for i in cable_group.items)


def test_manual_panel_count_and_psh_fallback_lower_confidence():
    photo_report = run_design(_demo_inputs())
    degraded_report = run_design(
        _demo_inputs(panel_count_source="manual", state="Nowhereland", has_supplier_quote=False)
    )
    assert degraded_report.confidence.score < photo_report.confidence.score


def test_auto_select_inverter_from_catalog():
    catalog = (HUAWEI_10KW,)
    report = run_design(_demo_inputs(inverter=None, inverter_catalog=catalog))
    assert report.inverter.selected_by == "auto"
    assert report.inverter.model == "SUN2000-10KTL-M1"


def test_as_dict_matches_ard_shape_top_level_keys():
    report = run_design(_demo_inputs())
    d = report.as_dict()
    expected_keys = {
        "id", "project_id", "system_type", "status", "generated_at", "confidence",
        "site", "load", "array", "strings", "inverter", "battery", "bos",
        "financial", "equipment_tier", "warnings", "assumptions",
    }
    assert expected_keys <= set(d.keys())
