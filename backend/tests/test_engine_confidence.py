"""Confidence score model. Spec §9 (PRD bands win, ARD §4.9). ARD §4.11 row
"confidence cap"."""
import itertools

import pytest

from app.engine import confidence
from app.engine.types import ConfidenceSignals

ALL_TRUE = ConfidenceSignals(
    supplier_quote_attached=True,
    string_validated_pass=True,
    site_specifics_recorded=True,
    real_consumption_on_record=True,
    manual_panel_count=False,
    psh_is_fallback=False,
)
BASELINE = ConfidenceSignals(
    supplier_quote_attached=False,
    string_validated_pass=False,
    site_specifics_recorded=False,
    real_consumption_on_record=False,
    manual_panel_count=False,
    psh_is_fallback=False,
)
WORST_CASE = ConfidenceSignals(
    supplier_quote_attached=False,
    string_validated_pass=False,
    site_specifics_recorded=False,
    real_consumption_on_record=False,
    manual_panel_count=True,
    psh_is_fallback=True,
)


def test_baseline_is_85():
    result = confidence.score_confidence(BASELINE)
    assert result.score == 85


def test_best_case_hard_capped_at_94_never_100():
    """85 (base) + 3 + 3 + 2 + 1 = 94 exactly — the additive sum happens to
    hit the cap here, but the cap itself is asserted independently below
    across every possible signal combination so this isn't a coincidence."""
    result = confidence.score_confidence(ALL_TRUE)
    assert result.score == 94
    assert result.score < 100


def test_worst_case_floored_and_never_negative():
    result = confidence.score_confidence(WORST_CASE)
    assert result.score == 85 - 10 - 4
    assert result.score >= 60


def test_confidence_never_exceeds_94_under_any_signal_combination():
    """ARD §4.11: never emit 95+, never 100, under any input combination."""
    fields = [
        "supplier_quote_attached", "string_validated_pass", "site_specifics_recorded",
        "real_consumption_on_record", "manual_panel_count", "psh_is_fallback",
    ]
    for combo in itertools.product([True, False], repeat=len(fields)):
        signals = ConfidenceSignals(**dict(zip(fields, combo)))
        result = confidence.score_confidence(signals)
        assert result.score <= 94
        assert result.score < 100
        assert result.score >= 60


def test_disclaimer_always_present():
    for signals in (ALL_TRUE, BASELINE, WORST_CASE):
        result = confidence.score_confidence(signals)
        assert result.disclaimer == "AI-estimated, installer-confirmed"


def test_components_list_reports_every_row_including_unapplied():
    result = confidence.score_confidence(BASELINE)
    labels = {c.label for c in result.components}
    assert labels == {
        "Base", "Supplier quote", "String validation", "Site specifics",
        "Consumption", "Manual count", "PSH fallback",
    }
    applied_labels = {c.label for c in result.components if c.applied}
    assert applied_labels == {"Base"}


@pytest.mark.parametrize(
    "score,expected_band",
    [(65, "Indicative"), (82, "Good estimate"), (87, "Solid — suitable for quotation"), (92, "Detailed specification — installer to confirm string design")],
)
def test_band_thresholds(score, expected_band):
    assert confidence._band(score) == expected_band
