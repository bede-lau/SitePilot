"""Confidence score model. Spec §9 (PRD bands win per ARD §4.9). ARD §4.9.

Additive, transparent, and hard-capped at 94 — never 95+, never 100 (a site
visit is always required for a final design; showing 100% would be dishonest
and creates liability, per the spec's own callout).
"""
from __future__ import annotations

from .types import ConfidenceComponent, ConfidenceScore, ConfidenceSignals

BASE_SCORE = 85
HARD_CAP = 94
HARD_FLOOR = 60

DISCLAIMER = "AI-estimated, installer-confirmed"


def _band(score: int) -> str:
    if score < 80:
        return "Indicative"
    if score <= 84:
        return "Good estimate"
    if score <= 89:
        return "Solid — suitable for quotation"
    return "Detailed specification — installer to confirm string design"


def score_confidence(signals: ConfidenceSignals) -> ConfidenceScore:
    """ARD §4.9 additive model. Every row is reported in ``components``
    (whether ``applied`` or not) so the UI can show the full breakdown on
    hover, not just the deltas that counted."""
    rows: list[tuple[str, int, bool, str]] = [
        (
            "Base",
            BASE_SCORE,
            True,
            "Panel count verified from a field photo + standard parameters",
        ),
        (
            "Supplier quote",
            3,
            signals.supplier_quote_attached,
            "A parsed vendor quote is attached with real unit pricing",
        ),
        (
            "String validation",
            3,
            signals.string_validated_pass,
            "String configuration validated PASS against a catalogued inverter",
        ),
        (
            "Site specifics",
            2,
            signals.site_specifics_recorded,
            "Tilt/azimuth/shading recorded (not engine defaults)",
        ),
        (
            "Consumption",
            1,
            signals.real_consumption_on_record,
            "Real monthly kWh on record",
        ),
        (
            "Manual count",
            -10,
            signals.manual_panel_count,
            "Panel count typed by hand, no field photo",
        ),
        (
            "PSH fallback",
            -4,
            signals.psh_is_fallback,
            "State-average PSH with no site-specific irradiance",
        ),
    ]

    total = sum(delta for _, delta, applied, _ in rows if applied)
    score = max(HARD_FLOOR, min(HARD_CAP, total))

    components = tuple(
        ConfidenceComponent(label=label, delta=delta, applied=applied, reason=reason)
        for label, delta, applied, reason in rows
    )

    return ConfidenceScore(
        score=score,
        band=_band(score),
        disclaimer=DISCLAIMER,
        components=components,
    )
