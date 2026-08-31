"""Inverter selection & validation. Spec §5 Stage 4 / ARD §4.5."""
import pytest

from app.engine import inverter
from app.engine.types import InverterSpec

INVERTER_5KW = InverterSpec(
    manufacturer="Generic", model="5kW grid-tie", ac_rating_kw=5, max_dc_input_kw=7,
    mppt_min_v=120, mppt_max_v=500, max_dc_voltage_v=1000,
    max_input_current_per_mppt_a=15, mppt_count=2, phase="single",
)
INVERTER_10KW_HUAWEI = InverterSpec(
    manufacturer="Huawei", model="SUN2000-10KTL-M1", ac_rating_kw=10, max_dc_input_kw=13,
    mppt_min_v=120, mppt_max_v=500, max_dc_voltage_v=1080,
    max_input_current_per_mppt_a=26, mppt_count=2, phase="three",
)


def test_target_ac_kw_and_dc_ac_ratio_worked_example():
    """Spec §5 Stage 4 worked example: 6.05 kWp / 1.5 = 4.03 kW target."""
    target = inverter.target_ac_kw(6.05, ratio=1.5)
    assert target == pytest.approx(4.03, rel=0.02)
    ratio = inverter.dc_ac_ratio(6.05, 4)
    assert ratio == pytest.approx(1.5125, rel=0.02)


def test_select_inverter_picks_smallest_satisfying_candidate():
    """6.05 kWp / DCAC_RATIO_DEFAULT(1.25) -> target 4.84 kW; the 5kW
    candidate covers that (and the DC:AC band) while the 10kW Huawei is
    needlessly larger, so the smaller one wins."""
    catalog = (INVERTER_5KW, INVERTER_10KW_HUAWEI)
    chosen_spec, selection = inverter.select_inverter(6.05, catalog, tier="mid", system_type="on_grid")
    assert chosen_spec.model == "5kW grid-tie"
    assert selection.selected_by == "auto"
    assert all(c.passed for c in selection.checks)


def test_validate_inverter_reports_checks_for_named_inverter():
    """PRD §6 demo: manager names a 10kW Huawei explicitly. Array here is
    11 kWp -> DC:AC ratio 1.1, just under the official 1.2 floor -> the
    ratio-band check itself reports failed=True (transparent), even though
    report.py doesn't let that alone fail the whole design (see report.py's
    status-aggregation docstring)."""
    selection = inverter.validate_inverter(11.0, INVERTER_10KW_HUAWEI)
    assert selection.selected_by == "user"
    assert selection.dc_ac_ratio == pytest.approx(1.1, rel=0.01)
    ratio_check = next(c for c in selection.checks if c.id == "dc_ac_ratio_band")
    assert ratio_check.passed is False
    dc_input_check = next(c for c in selection.checks if c.id == "max_dc_input_kw")
    assert dc_input_check.passed is True
    anti_island_check = next(c for c in selection.checks if c.id == "anti_islanding")
    assert anti_island_check.passed is True


def test_select_inverter_raises_on_empty_catalog():
    with pytest.raises(ValueError):
        inverter.select_inverter(5.0, (), tier="mid", system_type="on_grid")


def test_anti_islanding_check_fails_when_absent():
    no_ai = InverterSpec(
        manufacturer="Generic", model="no anti-islanding", ac_rating_kw=5, max_dc_input_kw=7,
        mppt_min_v=100, mppt_max_v=500, max_dc_voltage_v=800,
        max_input_current_per_mppt_a=15, mppt_count=1, phase="single", has_anti_islanding=False,
    )
    selection = inverter.validate_inverter(4.0, no_ai)
    check = next(c for c in selection.checks if c.id == "anti_islanding")
    assert check.passed is False
