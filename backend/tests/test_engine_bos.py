"""Auto-generated BOS protection spec. Spec §8 / ARD §4.7. ARD §4.11 row
"BOS fuse"."""
import pytest

from app.engine import bos, strings
from app.engine.types import InverterSpec, ModuleSpec

LONGI_550 = ModuleSpec(
    manufacturer="Longi", model="Hi-MO7 LR5-72HTH-550M",
    rated_wp=550, vmp=41.5, voc=49.6, imp=13.2, isc=14.0,
)
NARROW_WINDOW_INVERTER = InverterSpec(
    manufacturer="Generic", model="100-200V narrow-window ref inverter",
    ac_rating_kw=3, max_dc_input_kw=5,
    mppt_min_v=100, mppt_max_v=200, max_dc_voltage_v=600,
    max_input_current_per_mppt_a=40, mppt_count=2, phase="single",
)


def _items(spec, group_name):
    group = next(g for g in spec.groups if g.group == group_name)
    return {i.item: i for i in group.items}


def test_bos_fuse_worked_example():
    """Spec §8: 1.25 x 14.0A Isc = 17.5A -> next standard size (20A)."""
    sd = strings.design_strings(15, LONGI_550, NARROW_WINDOW_INVERTER)
    spec = bos.generate_bos_spec(sd, NARROW_WINDOW_INVERTER, "on_grid")
    fuse = _items(spec, "DC Protection")["String DC fuse"]
    assert fuse.rating == "20 A gPV"
    assert "17.5" in fuse.note


def test_combiner_box_required_when_more_than_two_strings():
    sd = strings.design_strings(15, LONGI_550, NARROW_WINDOW_INVERTER)  # 3S x 5P
    spec = bos.generate_bos_spec(sd, NARROW_WINDOW_INVERTER, "on_grid")
    combiner = _items(spec, "DC Protection")["DC combiner box"]
    assert combiner.rating == "Required"


def test_combiner_box_not_required_for_two_or_fewer_strings():
    two_string_inverter = InverterSpec(
        manufacturer="Generic", model="wide window", ac_rating_kw=6, max_dc_input_kw=8,
        mppt_min_v=100, mppt_max_v=500, max_dc_voltage_v=1000,
        max_input_current_per_mppt_a=30, mppt_count=2, phase="single",
    )
    sd = strings.design_strings(16, LONGI_550, two_string_inverter)
    assert sd.parallel <= 2
    spec = bos.generate_bos_spec(sd, two_string_inverter, "on_grid")
    combiner = _items(spec, "DC Protection")["DC combiner box"]
    assert combiner.rating == "Not required"


def test_hybrid_adds_dc_battery_cable_on_grid_does_not():
    sd = strings.design_strings(15, LONGI_550, NARROW_WINDOW_INVERTER)
    hybrid_spec = bos.generate_bos_spec(sd, NARROW_WINDOW_INVERTER, "hybrid")
    on_grid_spec = bos.generate_bos_spec(sd, NARROW_WINDOW_INVERTER, "on_grid")

    hybrid_items = _items(hybrid_spec, "Cables")
    on_grid_items = _items(on_grid_spec, "Cables")

    assert "DC battery cable (battery to inverter)" in hybrid_items
    assert "DC battery cable (battery to inverter)" not in on_grid_items


def test_ac_mcb_three_phase_worked_example():
    """10kW three-phase: I = 10000 / (415 x sqrt(3) x 0.95) ~= 14.65A -> next
    standard size 16A."""
    huawei = InverterSpec(
        manufacturer="Huawei", model="SUN2000-10KTL-M1", ac_rating_kw=10, max_dc_input_kw=13,
        mppt_min_v=120, mppt_max_v=500, max_dc_voltage_v=1080,
        max_input_current_per_mppt_a=26, mppt_count=2, phase="three",
    )
    sd = strings.design_strings(15, LONGI_550, huawei)
    spec = bos.generate_bos_spec(sd, huawei, "on_grid")
    mcb = _items(spec, "AC Protection")["AC MCB"]
    assert mcb.rating == "16 A"


def test_anti_islanding_note_flags_when_absent():
    no_ai = InverterSpec(
        manufacturer="Generic", model="no anti-islanding", ac_rating_kw=5, max_dc_input_kw=7,
        mppt_min_v=100, mppt_max_v=500, max_dc_voltage_v=800,
        max_input_current_per_mppt_a=15, mppt_count=1, phase="single", has_anti_islanding=False,
    )
    sd = strings.design_strings(10, LONGI_550, no_ai)
    spec = bos.generate_bos_spec(sd, no_ai, "on_grid")
    item = _items(spec, "AC Protection")["Anti-islanding protection"]
    assert "NOT present" in item.note


def test_all_standards_are_from_the_allowed_set():
    allowed = {"IEC 62548", "IEC 60364", "TNB TCG", "MS IEC 60947"}
    sd = strings.design_strings(15, LONGI_550, NARROW_WINDOW_INVERTER)
    spec = bos.generate_bos_spec(sd, NARROW_WINDOW_INVERTER, "hybrid")
    for group in spec.groups:
        for item in group.items:
            assert item.standard in allowed
