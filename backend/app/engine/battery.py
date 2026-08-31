"""Hybrid battery sizing. Spec §6 Stage 4/5 (hybrid only — off-grid is out of
scope per ARD D5 and raises ``UnsupportedSystemType``). ARD §4.6.

Deviates from the ARD's stated default margin (1.12) — that figure is the
*off-grid* safety margin (spec §4 Stage 4B). The spec's own hybrid worked
example (§6 Stage 5C: "Battery Final (kWh) = Battery Energy × 1.10") and this
package's ``constants.BATTERY_SAFETY_MARGIN_HYBRID`` (already landed, with a
docstring citing that exact clause) both say 1.10. Since this module is
hybrid-only, the default here follows the hybrid constant/formula, not the
ARD prose's evidently-copied off-grid figure.
"""
from __future__ import annotations

import math

from . import constants
from .types import BatteryDesign, BatteryModuleSelection, Check


class UnsupportedSystemType(Exception):
    """Raised for any off-grid request — explicitly out of scope (ARD D5)."""


def _select_modules(required_kwh: float) -> tuple[BatteryModuleSelection, ...]:
    """Nearest standard LFP module size >= requirement (spec §6 Stage 5D); if
    the requirement exceeds the largest standard module, stack multiples of
    the largest size."""
    if required_kwh <= 0:
        smallest = constants.LFP_MODULES_KWH[0]
        return (BatteryModuleSelection(count=1, module_kwh=smallest, total_kwh=smallest),)

    for module_kwh in constants.LFP_MODULES_KWH:
        if module_kwh >= required_kwh:
            return (BatteryModuleSelection(count=1, module_kwh=module_kwh, total_kwh=module_kwh),)

    largest = constants.LFP_MODULES_KWH[-1]
    count = math.ceil(required_kwh / largest)
    return (BatteryModuleSelection(count=count, module_kwh=largest, total_kwh=round(count * largest, 3)),)


def size_hybrid_battery(
    critical_load_kw: float,
    backup_hours: float,
    dod: float = constants.LIFEPO4_DOD,
    margin: float = constants.BATTERY_SAFETY_MARGIN_HYBRID,
) -> BatteryDesign:
    """Spec §6 Stage 5. ``Battery Energy (kWh) = Critical Load (kW) × Backup
    Hours / DoD``, then a safety margin, then a C-rate check that grows the
    battery further if needed (never shrinks it) so the discharge rate stays
    at or below ``constants.BATTERY_MAX_C_RATE`` (0.8C)."""
    raw_kwh = (critical_load_kw * backup_hours) / dod if dod else 0.0
    final_kwh = raw_kwh * margin

    c_rate = (critical_load_kw / final_kwh) if final_kwh > 0 else 0.0
    if c_rate > constants.BATTERY_MAX_C_RATE:
        final_kwh = critical_load_kw / constants.BATTERY_MAX_C_RATE
        c_rate = constants.BATTERY_MAX_C_RATE

    ah_at_48v = (final_kwh * 1000) / constants.SYSTEM_VOLTAGE_DC

    modules = _select_modules(final_kwh)
    total_selected_kwh = sum(m.total_kwh for m in modules)
    usable_kwh = total_selected_kwh * dod

    c_rate_pass = c_rate <= constants.BATTERY_MAX_C_RATE + 1e-9
    checks = (
        Check(
            id="c_rate",
            label="Battery discharge C-rate within limit",
            expected=f"<= {constants.BATTERY_MAX_C_RATE}C",
            actual=round(c_rate, 3),
            unit="C",
            passed=c_rate_pass,
            margin_pct=round((constants.BATTERY_MAX_C_RATE - c_rate) / constants.BATTERY_MAX_C_RATE * 100, 1),
        ),
    )

    return BatteryDesign(
        critical_load_kw=round(critical_load_kw, 3),
        backup_hours=backup_hours,
        raw_kwh=round(raw_kwh, 3),
        final_kwh=round(final_kwh, 3),
        ah_at_48v=round(ah_at_48v, 1),
        modules=modules,
        usable_kwh=round(usable_kwh, 3),
        c_rate=round(c_rate, 3),
        checks=checks,
    )
