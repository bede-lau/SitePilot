"""TNB bill breakdown, savings and payback. Spec §5 Stage 6, §12.1, §12.3. ARD §4.8.

The spec's own worked example (§5 Stage 6: "effective tariff RM 0.47") is a
rounded figure lifted from the illustrative §12.2 blended-rate table, not
derived from the block formula in §12.1/§3.3. Per the ARD's own instruction
("follow the FORMULA, note the discrepancy — never fudge a constant to match
a worked example"), ``effective_tariff_myr_per_kwh`` here always computes the
rate from the actual TNB block schedule via ``tnb_bill_myr`` rather than
hard-coding RM 0.47 — the two land within a few percent for the worked
example's inputs but are not forced to match exactly (see
``test_engine_financial.py``).

Commercial tariffs have no published block schedule in the spec (only the two
flat RP4 "generation charge" bands, §3.3/§12.1) — this module uses that flat
per-kWh rate as the commercial "energy" component and layers the same
capacity/network/ICPT/retail add-ons on top as domestic (those are stated as
"all users" in §3.3), which is a judgment call, not a spec citation.
"""
from __future__ import annotations

from typing import Optional

from . import constants
from .types import BillBreakdown, FinancialModel, ProjectionYear


def tnb_bill_myr(kwh: float, category: str = "domestic") -> BillBreakdown:
    """Spec §12.1 / §3.3. Blocks (domestic) or flat RP4 rate (commercial),
    plus capacity + network + ICPT + retail (waived <= 600 kWh/month)."""
    if kwh <= 0:
        return BillBreakdown(
            kwh=0.0, energy_myr=0.0, capacity_myr=0.0, network_myr=0.0,
            icpt_myr=0.0, retail_myr=0.0, total_myr=0.0,
        )

    if category == "commercial":
        rate_sen = (
            constants.TNB_RP4_GEN_SEN_HIGH
            if kwh > constants.TNB_RP4_COMMERCIAL_THRESHOLD_KWH
            else constants.TNB_RP4_GEN_SEN_LOW
        )
        energy_myr = kwh * rate_sen / 100
    else:
        energy_myr = 0.0
        remaining = kwh
        prev_upper = 0.0
        for upper, rate_sen in constants.TNB_BLOCKS_DOMESTIC:
            band_kwh = min(remaining, upper - prev_upper)
            if band_kwh > 0:
                energy_myr += band_kwh * rate_sen / 100
                remaining -= band_kwh
            prev_upper = upper
            if remaining <= 0:
                break

    capacity_myr = kwh * constants.CAPACITY_CHARGE_SEN / 100
    network_myr = kwh * constants.NETWORK_CHARGE_SEN / 100
    icpt_myr = kwh * constants.ICPT_SEN / 100
    retail_myr = 0.0 if kwh <= constants.RETAIL_CHARGE_WAIVER_KWH else constants.RETAIL_CHARGE_MYR
    total_myr = energy_myr + capacity_myr + network_myr + icpt_myr + retail_myr

    return BillBreakdown(
        kwh=round(kwh, 2),
        energy_myr=round(energy_myr, 2),
        capacity_myr=round(capacity_myr, 2),
        network_myr=round(network_myr, 2),
        icpt_myr=round(icpt_myr, 2),
        retail_myr=round(retail_myr, 2),
        total_myr=round(total_myr, 2),
    )


def effective_tariff_myr_per_kwh(kwh: float, category: str = "domestic") -> float:
    """Blended RM/kWh implied by ``tnb_bill_myr`` at this consumption level."""
    if kwh <= 0:
        return 0.0
    return round(tnb_bill_myr(kwh, category).total_myr / kwh, 4)


def _cost_range(system_type: str, tier: str) -> tuple[float, float]:
    return constants.COST_RANGES_MYR.get(
        (system_type, tier), constants.COST_RANGES_MYR[("on_grid", "mid")]
    )


def run_financials(
    array_kwp: float,
    psh: float,
    eff: float,
    monthly_kwh: Optional[float],
    system_cost_myr: Optional[float],
    tier: str,
    system_type: str = "on_grid",
    tariff_category: str = "domestic",
) -> FinancialModel:
    """Spec §5 Stage 6. ARD §4.8.

    Self-consumption uses the same "design daily" (safety-factor-inflated)
    baseline as ``array.py``'s Stage 3C self-consumption check — not the raw
    metered ``monthly_kwh`` — so this module's self-consumed/exported split
    is consistent with the ``array`` section of the same report (both derive
    from ``monthly_kwh × SAFETY_FACTOR_LOAD``). Without any consumption on
    record, this assumes 100% self-consumption (no export) as the
    best-available estimate.
    """
    monthly_generation_kwh = array_kwp * psh * eff * 30

    if monthly_kwh is not None:
        design_monthly_kwh = monthly_kwh * constants.SAFETY_FACTOR_LOAD
        self_consumed = min(monthly_generation_kwh, design_monthly_kwh)
        exported = max(0.0, monthly_generation_kwh - design_monthly_kwh)
        tariff_baseline_kwh = monthly_kwh
    else:
        self_consumed = monthly_generation_kwh
        exported = 0.0
        tariff_baseline_kwh = monthly_generation_kwh

    effective_tariff = effective_tariff_myr_per_kwh(tariff_baseline_kwh, tariff_category)

    self_consumed_savings = self_consumed * effective_tariff
    export_credit = exported * constants.ATAP_SMP_MYR
    monthly_savings = self_consumed_savings + export_credit
    annual_savings = monthly_savings * 12

    cost_low, cost_high = _cost_range(system_type, tier)
    cost = system_cost_myr if system_cost_myr is not None else (cost_low + cost_high) / 2

    if annual_savings > 0:
        payback_years = cost / annual_savings
        payback_range = (round(payback_years * 0.85, 1), round(payback_years * 1.20, 1))
    else:
        payback_years = float("inf")
        payback_range = (float("inf"), float("inf"))

    bill_before = tnb_bill_myr(tariff_baseline_kwh, tariff_category).total_myr
    bill_after_kwh = max(0.0, tariff_baseline_kwh - self_consumed)
    bill_after = tnb_bill_myr(bill_after_kwh, tariff_category).total_myr

    projection: list[ProjectionYear] = []
    cumulative_savings = 0.0
    for year in range(1, constants.PROJECTION_YEARS + 1):
        degrade = (1 - constants.MODULE_DEGRADATION_PCT_PER_YEAR / 100) ** (year - 1)
        escalate = (1 + constants.TARIFF_ESCALATION_PCT_PER_YEAR / 100) ** (year - 1)
        cumulative_savings += annual_savings * degrade * escalate
        projection.append(
            ProjectionYear(
                year=year,
                cumulative_savings=round(cumulative_savings, 2),
                cumulative_net=round(cumulative_savings - cost, 2),
            )
        )

    assumptions = (
        f"{constants.MODULE_DEGRADATION_PCT_PER_YEAR}%/yr module degradation",
        f"{constants.TARIFF_ESCALATION_PCT_PER_YEAR}%/yr tariff escalation",
        "No export credit rollover (Solar ATAP)",
    )

    return FinancialModel(
        monthly_generation_kwh=round(monthly_generation_kwh, 2),
        effective_tariff_myr=effective_tariff,
        monthly_savings_myr=round(monthly_savings, 2),
        annual_savings_myr=round(annual_savings, 2),
        bill_before_myr=round(bill_before, 2),
        bill_after_myr=round(bill_after, 2),
        system_cost_myr=round(cost, 2),
        cost_range_myr=(cost_low, cost_high),
        payback_years=round(payback_years, 1) if annual_savings > 0 else payback_years,
        payback_range_years=payback_range,
        export_kwh=round(exported, 2),
        export_rate_myr=constants.ATAP_SMP_MYR,
        rollover=constants.EXPORT_ROLLOVER,
        projection=tuple(projection),
        assumptions=assumptions,
    )
