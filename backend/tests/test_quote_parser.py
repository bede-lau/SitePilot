"""Offline tests for `app/agents/quote_parser.py` — no network, no LLM calls.

Feeds canned "vision LLM" payloads straight into the normalisation pipeline
(`_normalise_line_item` / `_finalise`) so these exercise exactly the same code
`parse_quote()` runs after a real vision call, without needing one.

Run with:
    cd backend && venv/Scripts/python.exe -m pytest tests/test_quote_parser.py -q
"""
import io

import pytest
from PIL import Image

from app.agents import quote_parser
from app.agents.quote_parser import (
    _canon_currency,
    _canon_unit,
    _categorise,
    _extract_wattage_from_text,
    _finalise,
    _normalise_line_item,
    _stub_parse_quote,
    parse_quote,
)

FX_RATE = 4.72


# --------------------------------------------------------------------------
# Unit harmonisation
# --------------------------------------------------------------------------

def test_canon_unit_clean_spellings_not_ambiguous():
    for raw in ("pcs", "set", "lot", "Pcs", "SET"):
        canon, ambiguous = _canon_unit(raw)
        assert canon in ("pcs", "set", "lot")
        assert ambiguous is False


def test_canon_unit_abbreviations_canonicalise_and_flag_ambiguous():
    for raw, expected in (("nos", "pcs"), ("units", "pcs"), ("unit", "pcs"), ("pc", "pcs"), ("no", "pcs")):
        canon, ambiguous = _canon_unit(raw)
        assert canon == expected
        assert ambiguous is True


def test_canon_unit_missing_or_unknown_defaults_to_pcs_and_flags():
    canon, ambiguous = _canon_unit(None)
    assert (canon, ambiguous) == ("pcs", True)
    canon, ambiguous = _canon_unit("crates")
    assert (canon, ambiguous) == ("pcs", True)


# --------------------------------------------------------------------------
# Currency canonicalisation
# --------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["RM", "MYR", "Ringgit", "rm"])
def test_canon_currency_myr_variants(raw):
    assert _canon_currency(raw) == "MYR"


@pytest.mark.parametrize("raw", ["USD", "US$", "$", "usd"])
def test_canon_currency_usd_variants(raw):
    assert _canon_currency(raw) == "USD"


def test_canon_currency_missing_defaults_to_myr():
    assert _canon_currency(None) == "MYR"
    assert _canon_currency("") == "MYR"


# --------------------------------------------------------------------------
# Wattage extraction from prose
# --------------------------------------------------------------------------

def test_extract_wattage_from_description_prose():
    assert _extract_wattage_from_text("550Wp N-type TOPCon monocrystalline module") == 550
    assert _extract_wattage_from_text("575W Tiger Neo N-type module") == 575
    assert _extract_wattage_from_text("Rated 600 Watt bifacial panel") == 600


def test_extract_wattage_returns_none_when_absent_or_out_of_range():
    assert _extract_wattage_from_text("10kW three-phase string inverter") is None
    assert _extract_wattage_from_text("Aluminium mounting rail set") is None
    assert _extract_wattage_from_text("") is None


# --------------------------------------------------------------------------
# Categorisation
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "manufacturer,model,description,expected",
    [
        ("Longi", "Hi-MO7 LR5-72HTH-550M", "550Wp N-type TOPCon monocrystalline module", "module"),
        ("Huawei", "SUN2000-10KTL-M1", "10kW three-phase string inverter", "inverter"),
        ("BYD", "HVS 10.2", "Lithium battery energy storage module", "battery"),
        (None, None, "Type 2 DC surge protection device + MC4 combiner box", "bos"),
        (None, None, "Freight & delivery to site, installation and commissioning", "service"),
        (None, None, "Signage and site hoarding", "unknown"),
    ],
)
def test_categorise(manufacturer, model, description, expected):
    assert _categorise(manufacturer, model, description) == expected


# --------------------------------------------------------------------------
# Line-item normalisation: currency conversion + RM/Wp
# --------------------------------------------------------------------------

def test_normalise_myr_line_item_price_per_wp():
    raw = {
        "manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M",
        "description": "550Wp N-type TOPCon monocrystalline module", "quantity": 20, "unit": "pcs",
        "unit_price": 467.0, "currency": "MYR", "wattage_wp": 550, "warranty_years": 25, "lead_time_days": 21,
    }
    item, notes = _normalise_line_item(raw, 1, FX_RATE)
    assert item["category"] == "module"
    assert item["unit_price_myr"] == 467.0
    assert item["line_total_myr"] == pytest.approx(9340.00)
    assert item["price_per_wp_myr"] == pytest.approx(0.849, rel=1e-2)
    assert "CURRENCY_CONVERTED" not in item["flags"]
    assert notes == []


def test_normalise_usd_line_item_converts_and_flags():
    raw = {
        "manufacturer": "Jinko", "model": "Tiger Neo JKM575N-72HL4-BDV",
        "description": "575W Tiger Neo N-type module", "quantity": 24, "unit": "nos",
        "unit_price": 118.0, "currency": "USD", "wattage_wp": 575, "warranty_years": 25, "lead_time_days": 30,
    }
    item, notes = _normalise_line_item(raw, 4, FX_RATE)
    assert item["unit_price_myr"] == pytest.approx(118.0 * FX_RATE, rel=1e-6)
    assert item["line_total_myr"] == pytest.approx(24 * 118.0 * FX_RATE, rel=1e-6)
    assert "CURRENCY_CONVERTED" in item["flags"]
    assert "AMBIGUOUS_UNIT" in item["flags"]  # 'nos' is not a clean spelling
    assert any("converted from USD" in n for n in notes)
    assert any("unit ambiguous" in n for n in notes)


def test_normalise_wattage_pulled_from_description_when_column_missing():
    raw = {
        "manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M",
        "description": "550Wp N-type TOPCon monocrystalline module, black frame",
        "quantity": 10, "unit": "pcs", "unit_price": 450.0, "currency": "MYR",
        "wattage_wp": None, "warranty_years": 25, "lead_time_days": 21,
    }
    item, _ = _normalise_line_item(raw, 1, FX_RATE)
    assert item["rated_wp"] == 550
    assert "MISSING_WATTAGE" not in item["flags"]


def test_normalise_missing_wattage_flags_module_line():
    raw = {
        "manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M",
        "description": "High efficiency monocrystalline module", "quantity": 10, "unit": "pcs",
        "unit_price": 450.0, "currency": "MYR", "wattage_wp": None, "warranty_years": 25, "lead_time_days": 21,
    }
    item, notes = _normalise_line_item(raw, 2, FX_RATE)
    assert item["rated_wp"] is None
    assert "MISSING_WATTAGE" in item["flags"]
    assert any("wattage not found" in n for n in notes)


def test_normalise_price_outlier_flag():
    raw = {
        "manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M",
        "description": "550Wp N-type TOPCon monocrystalline module", "quantity": 10, "unit": "pcs",
        "unit_price": 1000.0, "currency": "MYR", "wattage_wp": 550, "warranty_years": 25, "lead_time_days": 21,
    }
    item, notes = _normalise_line_item(raw, 3, FX_RATE)
    assert item["price_per_wp_myr"] == pytest.approx(1000 / 550, rel=1e-3)
    assert "PRICE_OUTLIER" in item["flags"]
    assert any("outside the typical" in n for n in notes)


def test_normalise_no_warranty_and_lead_time_flags_on_equipment_lines():
    raw = {
        "manufacturer": "Huawei", "model": "SUN2000-10KTL-M1",
        "description": "10kW three-phase string inverter", "quantity": 1, "unit": "unit",
        "unit_price": 6800.0, "currency": "MYR", "wattage_wp": None, "warranty_years": None, "lead_time_days": None,
    }
    item, _ = _normalise_line_item(raw, 2, FX_RATE)
    assert "NO_WARRANTY_STATED" in item["flags"]
    assert "NO_LEAD_TIME" in item["flags"]


def test_normalise_bos_line_skips_warranty_lead_time_flags():
    raw = {
        "manufacturer": None, "model": None,
        "description": "Aluminium mounting rail set, 4.2m incl. clamps", "quantity": 5, "unit": "set",
        "unit_price": 95.0, "currency": "MYR", "wattage_wp": None, "warranty_years": None, "lead_time_days": None,
    }
    item, _ = _normalise_line_item(raw, 3, FX_RATE)
    assert item["category"] == "bos"
    assert "NO_WARRANTY_STATED" not in item["flags"]
    assert "NO_LEAD_TIME" not in item["flags"]


def test_normalise_null_fields_never_guessed():
    raw = {
        "manufacturer": None, "model": None, "description": "Mystery line item",
        "quantity": None, "unit": None, "unit_price": None, "currency": None,
        "wattage_wp": None, "warranty_years": None, "lead_time_days": None,
    }
    item, _ = _normalise_line_item(raw, 1, FX_RATE)
    assert item["quantity"] is None
    assert item["unit_price"] is None
    assert item["unit_price_myr"] is None
    assert item["line_total_myr"] is None


# --------------------------------------------------------------------------
# BNEF tier matching (monkeypatched — Agent A's registry may not exist yet)
# --------------------------------------------------------------------------

def test_tier1_module_flags_not_tier1(monkeypatch):
    monkeypatch.setattr(quote_parser, "match_manufacturer", lambda name: (False, "Some Tier2 Co"))
    raw = {
        "manufacturer": "NoName Solar", "model": "XYZ-550", "description": "550Wp module",
        "quantity": 10, "unit": "pcs", "unit_price": 450.0, "currency": "MYR",
        "wattage_wp": 550, "warranty_years": 25, "lead_time_days": 21,
    }
    item, notes = _normalise_line_item(raw, 1, FX_RATE)
    assert item["bnef_tier1"] is False
    assert item["tier_match_name"] == "Some Tier2 Co"
    assert "NOT_TIER1" in item["flags"]
    assert any("not BNEF Tier 1" in n for n in notes)


def test_tier1_module_matched(monkeypatch):
    monkeypatch.setattr(quote_parser, "match_manufacturer", lambda name: (True, "LONGi Green Energy"))
    raw = {
        "manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M", "description": "550Wp module",
        "quantity": 20, "unit": "pcs", "unit_price": 467.0, "currency": "MYR",
        "wattage_wp": 550, "warranty_years": 25, "lead_time_days": 21,
    }
    item, _ = _normalise_line_item(raw, 1, FX_RATE)
    assert item["bnef_tier1"] is True
    assert item["tier_match_name"] == "LONGi Green Energy"
    assert "NOT_TIER1" not in item["flags"]
    assert "TIER_UNKNOWN" not in item["flags"]


def test_tier_unknown_when_registry_cannot_match(monkeypatch):
    monkeypatch.setattr(quote_parser, "match_manufacturer", lambda name: (None, None))
    raw = {
        "manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M", "description": "550Wp module",
        "quantity": 20, "unit": "pcs", "unit_price": 467.0, "currency": "MYR",
        "wattage_wp": 550, "warranty_years": 25, "lead_time_days": 21,
    }
    item, _ = _normalise_line_item(raw, 1, FX_RATE)
    assert item["bnef_tier1"] is None
    assert "TIER_UNKNOWN" in item["flags"]


def test_tier_check_only_applies_to_module_lines(monkeypatch):
    calls = []
    monkeypatch.setattr(quote_parser, "match_manufacturer", lambda name: calls.append(name) or (False, None))
    raw = {
        "manufacturer": "Huawei", "model": "SUN2000-10KTL-M1", "description": "10kW string inverter",
        "quantity": 1, "unit": "unit", "unit_price": 6800.0, "currency": "MYR",
        "wattage_wp": None, "warranty_years": 10, "lead_time_days": 14,
    }
    item, _ = _normalise_line_item(raw, 1, FX_RATE)
    assert calls == []  # never called for a non-module line
    assert item["bnef_tier1"] is None
    assert "NOT_TIER1" not in item["flags"]


# --------------------------------------------------------------------------
# _finalise: parse_status, subtotal, summary
# --------------------------------------------------------------------------

def _sample_payload(currency="MYR", unit_price=467.0):
    return {
        "supplier_name": "SunTech Materials Sdn Bhd",
        "line_items": [
            {
                "manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M",
                "description": "550Wp N-type TOPCon monocrystalline module", "quantity": 20, "unit": "pcs",
                "unit_price": unit_price, "currency": currency, "wattage_wp": 550,
                "warranty_years": 25, "lead_time_days": 21,
            }
        ],
    }


def test_finalise_parse_status_parsed_when_complete(monkeypatch):
    monkeypatch.setattr(quote_parser, "match_manufacturer", lambda name: (True, "LONGi Green Energy"))
    result = _finalise(_sample_payload(), "quote-suntech-aug26.pdf", FX_RATE, 2, "", None)
    assert result["parse_status"] == "parsed"
    assert result["supplier_name_raw"] == "SunTech Materials Sdn Bhd"
    assert result["subtotal_myr"] == pytest.approx(20 * 467.0)
    assert result["summary"]["tier1_line_count"] == 1
    assert result["summary"]["total_wp"] == 20 * 550


def test_finalise_parse_status_partial_when_fields_missing(monkeypatch):
    monkeypatch.setattr(quote_parser, "match_manufacturer", lambda name: (None, None))
    payload = {
        "supplier_name": "Demo Vendor",
        "line_items": [
            {"manufacturer": None, "model": None, "description": "Freight", "quantity": 1, "unit": "lot",
             "unit_price": 500.0, "currency": "MYR", "wattage_wp": None, "warranty_years": None, "lead_time_days": None}
        ],
    }
    result = _finalise(payload, "quote.pdf", FX_RATE, 1, "", None)
    assert result["parse_status"] == "partial"


def test_finalise_parse_status_failed_when_no_line_items():
    result = _finalise({"supplier_name": "Empty Co", "line_items": []}, "quote.pdf", FX_RATE, 1, "", None)
    assert result["parse_status"] == "failed"
    assert result["line_items"] == []
    assert result["subtotal_myr"] is None


def test_finalise_currency_conversion_marks_fx_rate(monkeypatch):
    monkeypatch.setattr(quote_parser, "match_manufacturer", lambda name: (True, "LONGi Green Energy"))
    result_myr = _finalise(_sample_payload(currency="MYR"), "quote.pdf", FX_RATE, 1, "", None)
    assert result_myr["fx_rate_to_myr"] == 1.0

    result_usd = _finalise(_sample_payload(currency="USD", unit_price=100.0), "quote.pdf", FX_RATE, 1, "", None)
    assert result_usd["fx_rate_to_myr"] == FX_RATE
    assert result_usd["line_items"][0]["unit_price_myr"] == pytest.approx(100.0 * FX_RATE)


# --------------------------------------------------------------------------
# Stub path — no LLM_API_KEY, app must stay fully demoable offline
# --------------------------------------------------------------------------

def test_stub_parse_quote_is_deterministic_per_filename():
    a = _stub_parse_quote("quote-suntech-aug26.pdf")
    b = _stub_parse_quote("quote-suntech-aug26.pdf")
    assert a == b
    assert a["line_items"]


def _tiny_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), color="white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_parse_quote_stub_path_when_no_api_key(monkeypatch):
    monkeypatch.setattr(quote_parser.settings, "llm_api_key", "")
    result = await parse_quote(_tiny_png_bytes(), "quote-demo.png")
    assert result["parse_status"] in ("parsed", "partial")
    assert result["line_items"]
    assert "Stub parse" in result["parse_notes"]
    assert result["page_count"] == 1
