"""TNB bill / savings / payback. Spec §5 Stage 6, §12.1, §12.3 / ARD §4.8.
ARD §4.11 row "financial".

See ``financial.py``'s module docstring: the spec's "effective tariff RM
0.47" is a rounded figure from the illustrative §12.2 blended-rate table, not
derived from the §12.1 block formula. This suite follows the FORMULA
(``tnb_bill_myr``) rather than forcing RM 0.47/kWh or the exact RM 204/RM 9
figures — see ``test_run_financials_worked_example_generation_and_range``
for the numbers that *are* formula-exact (monthly generation, payback as a
range, positive savings) vs. the numbers deliberately left loose.
"""
import pytest

from app.engine import constants, financial


def test_tnb_bill_domestic_blocks():
    """Spec §12.1: 250 kWh should land in block 3 (201-300 at 33.40 sen)
    after exhausting blocks 1-2, with capacity/network/ICPT layered on top
    and the RM10 retail charge waived (<=600 kWh)."""
    bill = financial.tnb_bill_myr(250, "domestic")
    # energy = 200*0.218 + 50*0.334 = 43.60 + 16.70 = 60.30
    assert bill.energy_myr == pytest.approx(60.30, rel=0.02)
    assert bill.retail_myr == 0.0
    assert bill.total_myr == pytest.approx(
        60.30 + 250 * constants.CAPACITY_CHARGE_SEN / 100
        + 250 * constants.NETWORK_CHARGE_SEN / 100
        + 250 * constants.ICPT_SEN / 100,
        rel=0.02,
    )


def test_tnb_bill_retail_charge_applies_above_waiver():
    bill = financial.tnb_bill_myr(700, "domestic")
    assert bill.retail_myr == constants.RETAIL_CHARGE_MYR


def test_tnb_bill_zero_kwh_is_zero():
    bill = financial.tnb_bill_myr(0, "domestic")
    assert bill.total_myr == 0.0


def test_effective_tariff_is_positive_and_bracket_sensitive():
    low = financial.effective_tariff_myr_per_kwh(150, "domestic")
    high = financial.effective_tariff_myr_per_kwh(1000, "domestic")
    assert 0 < low < high  # heavier usage -> higher blended rate


def test_run_financials_worked_example_generation_and_range():
    """Spec §5 Stage 6 worked example inputs: 6.05 kWp, PSH 4.5, eff 0.593,
    system cost RM 25,000 (mid on-grid). Monthly generation is formula-exact
    (484 kWh); payback must be shown as a distinct (low, high) range, never a
    single figure, and both bounds must be positive."""
    result = financial.run_financials(
        array_kwp=6.05, psh=4.5, eff=0.593, monthly_kwh=363,
        system_cost_myr=25000, tier="mid", system_type="on_grid", tariff_category="domestic",
    )
    assert result.monthly_generation_kwh == pytest.approx(484, rel=0.02)
    assert result.monthly_savings_myr > 0
    assert result.annual_savings_myr == pytest.approx(result.monthly_savings_myr * 12, rel=0.001)
    low, high = result.payback_range_years
    assert low < result.payback_years < high
    assert result.rollover is False
    assert "0.5%/yr module degradation" in result.assumptions[0]


def test_run_financials_no_consumption_assumes_full_self_consumption():
    result = financial.run_financials(
        array_kwp=6.05, psh=4.5, eff=0.593, monthly_kwh=None,
        system_cost_myr=25000, tier="mid",
    )
    assert result.export_kwh == 0.0


def test_run_financials_projection_reflects_degradation_and_escalation():
    result = financial.run_financials(
        array_kwp=6.05, psh=4.5, eff=0.593, monthly_kwh=363,
        system_cost_myr=25000, tier="mid",
    )
    assert len(result.projection) == constants.PROJECTION_YEARS
    # Escalation (+3%/yr) outpaces degradation (-0.5%/yr), so each year's
    # incremental savings (and hence the cumulative curve) keeps rising.
    year1 = result.projection[0].cumulative_savings
    year2 = result.projection[1].cumulative_savings
    assert year2 > year1 * 1.5  # not literally 2x (partial year1), but clearly growing
    assert result.projection[-1].cumulative_net == pytest.approx(
        result.projection[-1].cumulative_savings - result.system_cost_myr, rel=0.001
    )


def test_run_financials_defaults_cost_from_range_when_not_supplied():
    result = financial.run_financials(
        array_kwp=6.05, psh=4.5, eff=0.593, monthly_kwh=363,
        system_cost_myr=None, tier="mid", system_type="on_grid",
    )
    low, high = constants.COST_RANGES_MYR[("on_grid", "mid")]
    assert low <= result.system_cost_myr <= high


def test_commercial_uses_flat_rp4_rate():
    bill_low = financial.tnb_bill_myr(1000, "commercial")
    bill_high = financial.tnb_bill_myr(2000, "commercial")
    # per-kWh energy rate should step up past the 1500 kWh RP4 threshold
    rate_low = (bill_low.energy_myr) / 1000
    rate_high = (bill_high.energy_myr) / 2000
    assert rate_high > rate_low
