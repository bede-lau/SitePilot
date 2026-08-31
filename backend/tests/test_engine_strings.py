"""String (series/parallel) design. Spec §4 Stage 6 / ARD §4.4 — "the money
module". ARD §4.11 row "string design".

IMPORTANT — a documented spec-vs-algorithm discrepancy (found while writing
this test suite, not a bug introduced here):

The spec's own §4 Stage 6 worked example uses a Longi 550W module against a
"120-500V DC" MPPT inverter, computes ``series_max = FLOOR(500*0.85/49.6) =
8``, and then says "-> Use 3 series (practical for 48V system)" — a human,
un-formalised judgement call, not something derived from the three stated
validation checks. ARD §4.4 turns the *selection* into an explicit algorithm:
"search series counts from series_max downward for the largest that
satisfies all of [the three checks]". Those two don't agree: for a Longi
550W module, raising the series count strictly *lowers* the number of
parallel strings needed for a fixed panel count, which strictly *lowers*
total Isc — so every one of the three checks stays easier to satisfy at
series=8 than at series=3 (Vmp/Voc never fail for series 3..8; the current
check only gets easier going up). There is no per-string current limit that
makes the coded "search downward, take the first full pass" algorithm land
on 3 instead of 8 when the MPPT window is as wide as 120-500V — it will
always return series_max itself in that case, independent of panel count.

Since ``design_strings``/``series_max`` (this module) were already built and
are outside this agent's ownership, and the PRD's Huawei SUN2000-10KTL-M1
demo pairing is required to use exactly a 120-500V MPPT window, the actual
computed output for that pairing is 8S (not the PRD narrative's 3S×5P) — see
``test_engine_report.py``'s demo-case test, which asserts the real output and
explains the same thing there. This file's
``test_string_design_narrow_mppt_window_matches_worked_example`` below shows
the algorithm *does* correctly reproduce the spec's exact worked-example
numbers (124.5V / 148.8V / 3S×5P / 70A) once the inverter's MPPT window is
narrow enough that series_max itself is 3 — which is what a real single-phase
residential string inverter's MPPT window (much narrower than 500V) typically
looks like. Per the ARD's own instruction ("follow the FORMULA, note the
discrepancy — never fudge a constant to force a match"), this suite asserts
what the code actually computes, not the PRD's narrative figure.
"""
import pytest

from app.engine import strings
from app.engine.types import InverterSpec, ModuleSpec

LONGI_550 = ModuleSpec(
    manufacturer="Longi", model="Hi-MO7 LR5-72HTH-550M",
    rated_wp=550, vmp=41.5, voc=49.6, imp=13.2, isc=14.0,
)

WIDE_WINDOW_INVERTER = InverterSpec(
    manufacturer="Generic", model="120-500V ref inverter",
    ac_rating_kw=6, max_dc_input_kw=8,
    mppt_min_v=120, mppt_max_v=500, max_dc_voltage_v=1000,
    max_input_current_per_mppt_a=26, mppt_count=2, phase="single",
)

# A narrower, more typical residential single-string-input MPPT window —
# chosen so series_max computes to exactly 3 (the spec's own worked example).
NARROW_WINDOW_INVERTER = InverterSpec(
    manufacturer="Generic", model="100-200V narrow-window ref inverter",
    ac_rating_kw=3, max_dc_input_kw=5,
    mppt_min_v=100, mppt_max_v=200, max_dc_voltage_v=600,
    max_input_current_per_mppt_a=40, mppt_count=2, phase="single",
)


def test_series_max_worked_example():
    """Spec §4 Stage 6: FLOOR(500 x 0.85 / 49.6) = FLOOR(8.57) = 8."""
    assert strings.series_max(500, 49.6) == 8


def test_string_design_narrow_mppt_window_matches_worked_example():
    """With an inverter whose MPPT window makes series_max=3 (as the spec's
    hand-picked example implicitly assumes), the algorithm reproduces the
    spec's exact numbers: 3S x 5P for 15 panels, Vmp 124.5V, Voc 148.8V,
    total Isc 70A, all checks pass."""
    assert strings.series_max(200, 49.6) == 3

    sd = strings.design_strings(15, LONGI_550, NARROW_WINDOW_INVERTER)

    assert sd.status == "pass"
    assert sd.series == 3
    assert sd.parallel == 5
    assert sd.config_label == "3S × 5P"
    assert sd.panels_used == 15
    assert sd.orphan_panels == 0
    assert sd.vmp_string == pytest.approx(124.5, rel=0.02)
    assert sd.voc_string == pytest.approx(148.8, rel=0.02)
    assert sd.total_isc == pytest.approx(70.0, rel=0.02)
    assert all(c.passed for c in sd.checks)


def test_string_design_wide_mppt_window_selects_series_max_not_spec_narrative():
    """Documented discrepancy (see module docstring): a 120-500V MPPT window
    makes the "search downward, take the largest passing series" algorithm
    select series_max (8) rather than the PRD narrative's 3S — because at
    series=8 every check is *easier* to satisfy than at series=3 for a fixed
    panel count. This is the real, current behaviour of the already-built
    algorithm, asserted here deliberately (not the narrative's 3S/124.5V/
    148.8V) so a future change to either the algorithm or the demo's inverter
    spec shows up as a test failure, not a silent drift."""
    sd = strings.design_strings(15, LONGI_550, WIDE_WINDOW_INVERTER)

    assert sd.status == "pass"
    assert sd.series == 8
    assert sd.vmp_string == pytest.approx(332.0, rel=0.02)
    assert sd.voc_string == pytest.approx(396.8, rel=0.02)
    assert all(c.passed for c in sd.checks)


def test_string_design_fail_when_voc_exceeds_window_even_at_series_one():
    tiny_window = InverterSpec(
        manufacturer="Generic", model="tiny window", ac_rating_kw=1, max_dc_input_kw=1,
        mppt_min_v=10, mppt_max_v=20, max_dc_voltage_v=30,
        max_input_current_per_mppt_a=5, mppt_count=1, phase="single",
    )
    sd = strings.design_strings(4, LONGI_550, tiny_window)
    assert sd.status == "fail"
    assert sd.series == 1
    assert any(not c.passed for c in sd.checks)


def test_voc_cold_uses_temp_coefficient_when_available():
    module_with_coeff = ModuleSpec(
        manufacturer="Longi", model="Hi-MO7 LR5-72HTH-550M",
        rated_wp=550, vmp=41.5, voc=49.6, imp=13.2, isc=14.0,
        temp_coeff_voc_pct_per_c=-0.24,
    )
    sd = strings.design_strings(15, module_with_coeff, NARROW_WINDOW_INVERTER)
    assert sd.voc_method == "temp_coefficient"
    # Cooler-than-25C -> Voc rises -> cold Voc > nominal Voc.
    assert sd.voc_cold_string > sd.voc_string


def test_voc_cold_flat_buffer_when_no_temp_coefficient():
    sd = strings.design_strings(15, LONGI_550, NARROW_WINDOW_INVERTER)
    assert sd.voc_method == "flat_0.85_buffer"
    assert sd.voc_cold_string == sd.voc_string


def test_validate_inverter_matches_design_strings():
    sd1 = strings.design_strings(15, LONGI_550, NARROW_WINDOW_INVERTER)
    sd2 = strings.validate_inverter(15, LONGI_550, NARROW_WINDOW_INVERTER)
    assert sd1 == sd2
