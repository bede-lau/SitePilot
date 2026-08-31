"""Load calc + array sizing. Spec §5 Stages 1 & 3 / ARD §4.3. ARD §4.11 rows
"on-grid array sizing" and "self-consumption".
"""
import pytest

from app.engine import array
from app.engine.types import ModuleSpec

DEFAULT_MODULE = ModuleSpec(
    manufacturer="Generic", model="Standard 550W Reference Module",
    rated_wp=550.0, vmp=41.5, voc=49.6, imp=13.2, isc=14.0,
)


def test_design_daily_wh_worked_example():
    """Spec §5 Stage 1: 363 kWh/mo -> 12.1 kWh/day -> 14,520 Wh/day design load."""
    assert array.design_daily_wh(363) == pytest.approx(14520, rel=0.02)


def test_required_array_kwp_worked_example():
    """Spec §5 Stage 3A: 14,520 / (4.5 x 0.593 x 1000) ~= 5.44 kWp."""
    req = array.required_array_kwp(14520, psh=4.5, eff=0.593)
    assert req == pytest.approx(5.44, rel=0.02)


def test_on_grid_array_sizing_worked_example():
    """Spec §5 Stage 3 full worked example: 363 kWh/mo -> 14,520 Wh/day design
    -> 5.44 kWp required -> no roof constraint -> x1.10 margin = 5.98 kWp ->
    CEIL(5980/550) = 11 panels -> actual 6.05 kWp."""
    design_daily = array.design_daily_wh(363)
    sizing, flags = array.size_array(design_daily, psh=4.5, eff=0.593, max_roof_kwp=10.45, module=DEFAULT_MODULE)

    assert sizing.required_kwp == pytest.approx(5.44, rel=0.02)
    assert sizing.constrained is False
    assert sizing.panel_count == 11
    assert sizing.actual_kwp == pytest.approx(6.05, rel=0.02)


def test_self_consumption_worked_example():
    """Spec §5 Stage 3C: actual array 6.05 kWp -> daily generation 16.14 kWh,
    design daily 14.52 kWh -> self-consumed 14.52 kWh (100%), exported
    1.62 kWh (~10%, acceptable, no OVERSIZED warning)."""
    design_daily = array.design_daily_wh(363)  # -> 14,520 Wh -> 14.52 kWh design daily
    sizing, flags = array.array_from_panel_count(
        panel_count=11, module=DEFAULT_MODULE, psh=4.5, eff=0.593, design_daily_wh_=design_daily
    )
    assert sizing.daily_generation_kwh == pytest.approx(16.14, rel=0.02)
    assert sizing.self_consumed_kwh == pytest.approx(14.52, rel=0.02)
    assert sizing.exported_kwh == pytest.approx(1.62, rel=0.05)
    assert not any(f.code == "OVERSIZED" for f in flags)


def test_oversized_flag_when_export_exceeds_30_percent():
    # Large array vs. tiny design load -> most of the generation is exported.
    sizing, flags = array.array_from_panel_count(
        panel_count=40, module=DEFAULT_MODULE, psh=4.5, eff=0.6, design_daily_wh_=2000
    )
    assert sizing.exported_kwh > 0
    assert any(f.code == "OVERSIZED" for f in flags)


def test_roof_constrained_flag():
    design_daily = array.design_daily_wh(2000)  # a big load
    sizing, flags = array.size_array(design_daily, psh=4.3, eff=0.6, max_roof_kwp=3.0, module=DEFAULT_MODULE)
    assert sizing.constrained is True
    assert any(f.code == "ROOF_CONSTRAINED" for f in flags)
    assert sizing.coverage_pct < 100


def test_array_from_panel_count_epc_entry_point():
    """ARD §4.3 — the field CV count is authoritative; required_kwp is None."""
    sizing, flags = array.array_from_panel_count(panel_count=20, module=DEFAULT_MODULE, psh=4.35, eff=0.605625)
    assert sizing.required_kwp is None
    assert sizing.panel_count == 20
    assert sizing.actual_kwp == pytest.approx(11.0)
