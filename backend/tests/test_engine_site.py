"""Site & efficiency. Spec §4 Stage 2 / ARD §4.2. ARD §4.11 test table rows
"effective efficiency" and "roof max panels".
"""
import pytest

from app.engine import constants, site
from app.engine.types import Obstruction


def test_effective_efficiency_worked_example():
    """Spec §4 Stage 2D worked example: tilt 15°, azimuth 10°, shading 0.95
    -> 0.75 x 1.00 x 0.98 x 0.95 x 0.85 ~= 0.593."""
    eff = site.effective_efficiency(tilt_deg=15, azimuth_deg=10, shading_factor=0.95)
    assert eff.base == 0.75
    assert eff.tilt == 1.00
    assert eff.azimuth == 0.98
    assert eff.shading == 0.95
    assert eff.temperature == 0.85
    assert eff.effective == pytest.approx(0.593, rel=0.02)


def test_effective_efficiency_defaults_when_none():
    """ARD §3.1: null tilt/azimuth/shading fall back to 15deg/0deg/0.95."""
    eff = site.effective_efficiency(None, None, None)
    assert eff.tilt == 1.00  # 15 deg default -> band <=15
    assert eff.azimuth == 1.00  # 0 deg default -> true south
    assert eff.shading == 0.95


@pytest.mark.parametrize(
    "tilt,expected",
    [(5, 0.95), (15, 1.00), (20, 0.97), (30, 0.90)],
)
def test_tilt_factor_bands(tilt, expected):
    eff = site.effective_efficiency(tilt, 0, 1.0)
    assert eff.tilt == expected


@pytest.mark.parametrize(
    "azimuth,expected",
    [(0, 1.00), (20, 0.98), (40, 0.93), (60, 0.85), (80, 0.75)],
)
def test_azimuth_factor_bands(azimuth, expected):
    eff = site.effective_efficiency(15, azimuth, 1.0)
    assert eff.azimuth == expected


def test_azimuth_flag_beyond_90_degrees():
    flag = site.azimuth_flag(95)
    assert flag is not None
    assert flag.level == "warn"
    assert flag.code == "AZIMUTH_SUBOPTIMAL"


def test_azimuth_flag_within_90_is_none():
    assert site.azimuth_flag(80) is None
    assert site.azimuth_flag(None) is None


def test_roof_max_panels_worked_example():
    """Spec §4 Stage 2B/2C worked example: 42 m2 usable, 1 water tank (-2 m2)
    -> net 40 m2 -> FLOOR(40/2.1) = 19 panels -> 19 x 0.55 = 10.45 kWp."""
    net = site.net_usable_area(42, (Obstruction(kind="water_tank", count=1),))
    assert net == pytest.approx(40.0)
    max_panels = site.max_panels_from_roof(net)
    assert max_panels == 19
    max_kwp = max_panels * constants.DEFAULT_PANEL_WP / 1000
    assert max_kwp == pytest.approx(10.45, rel=0.02)


def test_net_usable_area_none_roof_area():
    assert site.net_usable_area(None, ()) is None
    assert site.max_panels_from_roof(None) is None


def test_psh_for_state_selangor_and_fallback():
    psh, is_fallback = constants.psh_for_state("Selangor")
    assert is_fallback is False
    assert 4.0 < psh < 4.6

    psh2, is_fallback2 = constants.psh_for_state("Neverland")
    assert is_fallback2 is True
    # Falls back to the Selangor figure (ARD default state).
    assert psh2 == psh
