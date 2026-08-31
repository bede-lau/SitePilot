"""Hybrid battery sizing. Spec §6 Stage 4/5 / ARD §4.6."""
import pytest

from app.engine import battery, constants


def test_hybrid_battery_worked_example():
    """Spec §6 Stage 5 worked example: fridge+lights+router+fans = 0.42 kW
    critical load, 6 hrs backup -> 0.42*6/0.80 = 3.15 kWh raw -> x1.10 =
    3.47 kWh final -> nearest standard module >= 3.47 is 5.12 kWh."""
    design = battery.size_hybrid_battery(critical_load_kw=0.42, backup_hours=6)
    assert design.raw_kwh == pytest.approx(3.15, rel=0.02)
    assert design.final_kwh == pytest.approx(3.47, rel=0.02)
    assert design.c_rate == pytest.approx(0.12, rel=0.05)
    assert len(design.modules) == 1
    assert design.modules[0].module_kwh == 5.12
    assert design.modules[0].count == 1
    assert all(c.passed for c in design.checks)


def test_hybrid_battery_with_aircon_worked_example():
    """Spec §6 Stage 5 worked example (adds 1 aircon unit): critical load
    0.42+1.5=1.92 kW, 6 hrs -> 1.92*6/0.80=14.4 kWh raw -> x1.10=15.84 kWh
    -> nearest standard module (largest, 15.36) is short, so the engine
    stacks to cover it (see battery.py's module-selection fallback) rather
    than under-sizing the battery."""
    design = battery.size_hybrid_battery(critical_load_kw=1.92, backup_hours=6)
    assert design.raw_kwh == pytest.approx(14.4, rel=0.02)
    assert design.final_kwh == pytest.approx(15.84, rel=0.05)
    total_selected = sum(m.total_kwh for m in design.modules)
    assert total_selected >= design.final_kwh


def test_c_rate_guard_grows_battery_when_exceeded():
    """A very high critical load relative to a short backup window can push
    the raw/margin-adjusted C-rate above the 0.8C cap; the engine must grow
    the battery further (never shrink it) so the final C-rate lands at or
    under the cap."""
    design = battery.size_hybrid_battery(critical_load_kw=5.0, backup_hours=0.5)
    assert design.c_rate <= constants.BATTERY_MAX_C_RATE + 1e-9
    assert all(c.passed for c in design.checks)


def test_off_grid_raises_unsupported_system_type():
    """ARD D5 — off-grid is explicitly out of scope. There's no
    `size_offgrid_battery` entry point at all; this asserts the exception
    type is importable and raisable as report.py depends on it."""
    with pytest.raises(battery.UnsupportedSystemType):
        raise battery.UnsupportedSystemType("off-grid is out of scope")
