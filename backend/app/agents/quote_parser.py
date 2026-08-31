"""Parses a messy supplier quotation (PDF or photographed image) into the
normalised structure the procurement UI renders — ARD.md §5.4 / §4.1.

Pipeline: render pages (+ text-layer hint) -> one vision call to
`settings.llm_vision_model` with a strict JSON prompt -> repair/retry once on
malformed JSON -> normalise (currency -> MYR, RM/Wp, unit harmonisation,
categorisation, BNEF tier check, flags). The LLM never does arithmetic here
either — every RM figure below is computed in Python from the raw fields it
returns.

`parse_quote()` never raises into the caller: any failure collapses into a
`parse_status: "failed"` result, same discipline as the rest of the stub/LLM
paths in this codebase (see `services/llm_client.py`).
"""
import base64
import json
import logging
import re
from collections import Counter
from pathlib import Path

from app.config import settings
from app.services import pdf_extract
from app.services.llm_client import _parse_json_response, get_client

logger = logging.getLogger("fieldbot.quote_parser")

DEFAULT_FX_RATE = 4.72

try:
    # Agent A's BNEF Tier 1 registry lookup — may not exist yet while it's being
    # built concurrently. Fall back to "unknown" rather than blocking on it.
    from app.data.bnef import match_manufacturer
except ImportError:  # pragma: no cover - exercised only before app/data/bnef.py lands
    def match_manufacturer(name: str) -> tuple[bool | None, str | None]:
        return (None, None)


# --------------------------------------------------------------------------
# Vision extraction
# --------------------------------------------------------------------------

QUOTE_VISION_PROMPT = """You are extracting structured data from a solar equipment supplier's price \
quotation. You are given one or more page images of the same document, in order, plus (if available) a \
raw text layer as an extra hint — the images are authoritative, the text layer may be empty or garbled.

The document is often messy on purpose: inconsistent table alignment, a row that wraps onto two lines, \
mixed units (pcs/nos/units/set/lot), one or two prices in USD with a footnote, wattage buried in \
description prose instead of its own column, warranty and lead time stated only in a free-text footnote, \
a handwritten-style annotation, a faint scanned-paper background, a "RECEIVED" stamp, and (for multi-page \
quotes) a page break mid-table with the column headers repeated. Read past all of that — extract the real \
line items underneath.

Return ONLY valid JSON (no markdown fences, no commentary) with exactly this shape:
{{
  "supplier_name": string or null,
  "line_items": [
    {{
      "manufacturer": string or null,
      "model": string or null,
      "description": string,
      "quantity": number or null,
      "unit": string or null,
      "unit_price": number or null,
      "currency": string or null,
      "wattage_wp": number or null,
      "warranty_years": number or null,
      "lead_time_days": number or null
    }}
  ]
}}

Field rules:
- One row per physical line item on the quote — never merge or split rows.
- "model": the vendor's own model string, verbatim, including any inconsistent formatting. Do not normalise it.
- "unit": exactly as printed on the page (e.g. "pcs", "nos", "set", "lot", "units").
- "currency": as stated near that line's price (e.g. "MYR", "RM", "USD", "US$", "$"); if the whole quote is \
in one currency stated only once (e.g. in the header), apply it to every line.
- "wattage_wp": pull this out of the description prose if it is not its own column (e.g. "550Wp N-type TOPCon" -> 550).
- "warranty_years" / "lead_time_days": these are often only stated once in a footnote, not per row — apply \
the footnote's value to the relevant equipment lines (modules, inverters, batteries) if that is clearly what it refers to.
- If a field is not stated anywhere or you are not confident, return null. Never guess a number.
- Ignore the letterhead, bank-details block, registration numbers, incoterms/validity clause, handwritten \
annotation, and any stamp — extract only the line items and the fields listed above.

Raw text layer (may be empty for a scanned page; use only as a hint, the images are ground truth):
\"\"\"
{raw_text}
\"\"\""""


async def _call_vision(images: list[bytes], prompt: str) -> str:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for img in images:
        data_uri = "data:image/png;base64," + base64.b64encode(img).decode()
        content.append({"type": "image_url", "image_url": {"url": data_uri}})
    response = await get_client().chat.completions.create(
        model=settings.llm_vision_model,
        messages=[{"role": "user", "content": content}],
        temperature=0,
    )
    return response.choices[0].message.content or ""


async def _extract_with_vision(images: list[bytes], raw_text: str) -> dict | None:
    prompt = QUOTE_VISION_PROMPT.format(raw_text=(raw_text or "")[:3000])
    last_text = ""
    for attempt in range(2):  # one retry on malformed JSON, per ARD §10 risk mitigation
        try:
            last_text = await _call_vision(images, prompt)
            return _parse_json_response(last_text)
        except (json.JSONDecodeError, IndexError, TypeError):
            logger.warning(
                "quote vision LLM returned unparseable JSON (attempt %d): %r",
                attempt + 1,
                last_text[:300],
            )
    return None


# --------------------------------------------------------------------------
# Normalisation helpers
# --------------------------------------------------------------------------

_UNIT_CANON = {
    "pcs": "pcs", "pc": "pcs", "piece": "pcs", "pieces": "pcs",
    "nos": "pcs", "no": "pcs", "unit": "pcs", "units": "pcs",
    "set": "set", "sets": "set",
    "lot": "lot", "lots": "lot",
}
_UNIT_CLEAN_SPELLING = {"pcs", "set", "lot"}  # printed exactly like this needs no assumption

_CURRENCY_CANON = {
    "RM": "MYR", "MYR": "MYR", "RINGGIT": "MYR",
    "USD": "USD", "US$": "USD", "$": "USD", "USDOLLAR": "USD", "U.S.D": "USD",
}

_MODULE_KEYWORDS = ("module", "panel", "mono", "topcon", "perc", "half-cut", "half cut", "bifacial", "n-type", "p-type")
_MODULE_BRANDS = ("longi", "jinko", "trina", "canadian solar", "ja solar", "risen", "astronergy", "hi-mo", "himo", "jasolar")
_INVERTER_KEYWORDS = ("inverter", "mppt", "sun2000", "string inverter", "hybrid inverter")
_INVERTER_BRANDS = ("huawei", "sma", "growatt", "sungrow", "solis", "goodwe", "deye", "fronius", "solaredge")
_BATTERY_KEYWORDS = ("battery", "batteries", "lfp", "lithium", "energy storage", "powerwall", "bess")
_BATTERY_BRANDS = ("byd", "pylontech", "dyness", "alpha ess")
_BOS_KEYWORDS = (
    "cable", "mc4", "breaker", "mcb", "spd", "combiner", "isolator", "fuse",
    "mounting", "rail", "clamp", "earthing", "grounding", "rccb", "surge",
)
_SERVICE_KEYWORDS = (
    "install", "labour", "labor", "commissioning", "design fee",
    "freight", "shipping", "delivery", "offload", "service", "testing",
)

_WATTAGE_RE = re.compile(r"(\d{2,4}(?:\.\d+)?)\s*W(?:p|att)?\b", re.IGNORECASE)

PRICE_OUTLIER_RANGE_MYR_PER_WP = (0.55, 1.60)


def _clean_str(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _to_number(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[,\s]", "", str(value))
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s in ("-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _canon_unit(raw_unit: str | None) -> tuple[str, bool]:
    """Returns (canonical_unit, is_ambiguous). Ambiguous means we had to assume
    what a non-standard abbreviation meant (e.g. "nos") rather than it already
    being one of the clean spellings pcs/set/lot."""
    if not raw_unit:
        return "pcs", True
    key = raw_unit.strip().lower().rstrip(".")
    canon = _UNIT_CANON.get(key)
    if canon is None:
        return "pcs", True
    return canon, key not in _UNIT_CLEAN_SPELLING


def _canon_currency(raw_currency: str | None) -> str:
    if not raw_currency:
        return "MYR"
    key = raw_currency.strip().upper().replace(" ", "")
    return _CURRENCY_CANON.get(key, key or "MYR")


def _extract_wattage_from_text(text: str) -> float | None:
    if not text:
        return None
    match = _WATTAGE_RE.search(text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if 50 <= value <= 1000 else None


def _categorise(manufacturer: str | None, model: str | None, description: str) -> str:
    haystack = " ".join(filter(None, [manufacturer, model, description])).lower()

    # Brand names are the least ambiguous signal, so check every category's
    # brand list before falling back to keyword prose — and check battery/
    # inverter ahead of module throughout, since "module" itself is generic
    # enough to appear in a battery description too (e.g. "battery module",
    # "energy storage module").
    if any(b in haystack for b in _BATTERY_BRANDS):
        return "battery"
    if any(b in haystack for b in _INVERTER_BRANDS):
        return "inverter"
    if any(b in haystack for b in _MODULE_BRANDS):
        return "module"
    if any(k in haystack for k in _BATTERY_KEYWORDS):
        return "battery"
    if any(k in haystack for k in _INVERTER_KEYWORDS):
        return "inverter"
    if any(k in haystack for k in _MODULE_KEYWORDS):
        return "module"
    if any(k in haystack for k in _BOS_KEYWORDS):
        return "bos"
    if any(k in haystack for k in _SERVICE_KEYWORDS):
        return "service"
    return "unknown"


def _sum_or_none(values) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals), 2) if vals else None


def _normalise_line_item(raw: dict, line_no: int, fx_rate: float) -> tuple[dict, list[str]]:
    notes: list[str] = []

    manufacturer = _clean_str(raw.get("manufacturer"))
    model = _clean_str(raw.get("model"))
    description = _clean_str(raw.get("description")) or ""

    quantity = _to_number(raw.get("quantity"))
    quantity = int(round(quantity)) if quantity is not None else None

    raw_unit = _clean_str(raw.get("unit"))
    unit, unit_ambiguous = _canon_unit(raw_unit)

    unit_price = _to_number(raw.get("unit_price"))
    currency = _canon_currency(_clean_str(raw.get("currency")))

    wattage = _to_number(raw.get("wattage_wp"))
    if wattage is None:
        wattage = _extract_wattage_from_text(description)
    rated_wp = int(round(wattage)) if wattage else None

    warranty_years = _to_number(raw.get("warranty_years"))
    lead_time_days = _to_number(raw.get("lead_time_days"))

    unit_price_myr = None
    if unit_price is not None:
        if currency == "USD":
            unit_price_myr = round(unit_price * fx_rate, 2)
        else:
            # MYR, or an unrecognised currency code we treat as already MYR rather than guess a rate.
            unit_price_myr = round(unit_price, 2)

    category = _categorise(manufacturer, model, description)

    price_per_wp_myr = None
    if category == "module" and rated_wp and unit_price_myr is not None:
        price_per_wp_myr = round(unit_price_myr / rated_wp, 3)

    line_total_myr = None
    if quantity is not None and unit_price_myr is not None:
        line_total_myr = round(quantity * unit_price_myr, 2)

    bnef_tier1 = None
    tier_match_name = None
    if category == "module" and manufacturer:
        bnef_tier1, tier_match_name = match_manufacturer(manufacturer)

    flags: list[str] = []

    if unit_ambiguous:
        flags.append("AMBIGUOUS_UNIT")
        notes.append(f"Line {line_no} unit ambiguous ('{raw_unit or ''}') — assumed pieces.")

    if currency != "MYR" and unit_price is not None:
        flags.append("CURRENCY_CONVERTED")
        notes.append(f"Line {line_no} price converted from {currency} at {fx_rate}.")

    if category == "module":
        if rated_wp is None:
            flags.append("MISSING_WATTAGE")
            notes.append(f"Line {line_no} wattage not found — check manually.")
        if bnef_tier1 is False:
            flags.append("NOT_TIER1")
            notes.append(f"Line {line_no} manufacturer '{manufacturer}' is not BNEF Tier 1.")
        elif bnef_tier1 is None and manufacturer:
            flags.append("TIER_UNKNOWN")
        if price_per_wp_myr is not None and not (
            PRICE_OUTLIER_RANGE_MYR_PER_WP[0] <= price_per_wp_myr <= PRICE_OUTLIER_RANGE_MYR_PER_WP[1]
        ):
            flags.append("PRICE_OUTLIER")
            notes.append(
                f"Line {line_no} RM/Wp {price_per_wp_myr} is outside the typical "
                f"{PRICE_OUTLIER_RANGE_MYR_PER_WP[0]}-{PRICE_OUTLIER_RANGE_MYR_PER_WP[1]} range."
            )

    if category in ("module", "inverter", "battery"):
        if warranty_years is None:
            flags.append("NO_WARRANTY_STATED")
        if lead_time_days is None:
            flags.append("NO_LEAD_TIME")

    item = {
        "line_no": line_no,
        "category": category,
        "manufacturer": manufacturer,
        "model": model,
        "description": description,
        "quantity": quantity,
        "unit": unit,
        "unit_price": unit_price,
        "currency": currency,
        "unit_price_myr": unit_price_myr,
        "line_total_myr": line_total_myr,
        "rated_wp": rated_wp,
        "price_per_wp_myr": price_per_wp_myr,
        "warranty_years": int(warranty_years) if warranty_years is not None else None,
        "lead_time_days": int(lead_time_days) if lead_time_days is not None else None,
        "bnef_tier1": bnef_tier1,
        "tier_match_name": tier_match_name,
        "flags": flags,
    }
    return item, notes


def _finalise(
    raw_payload: dict,
    filename: str,
    fx_rate: float,
    page_count: int,
    raw_text: str,
    raw_llm_json: dict | None,
) -> dict:
    supplier_name_raw = _clean_str(raw_payload.get("supplier_name")) or Path(filename).stem

    line_items: list[dict] = []
    notes: list[str] = []
    for i, raw_line in enumerate(raw_payload.get("line_items") or [], start=1):
        if not isinstance(raw_line, dict):
            continue
        item, line_notes = _normalise_line_item(raw_line, i, fx_rate)
        line_items.append(item)
        notes.extend(line_notes)

    currencies = [li["currency"] for li in line_items if li["currency"]]
    top_currency = Counter(currencies).most_common(1)[0][0] if currencies else "MYR"
    converted_any = any(li["currency"] != "MYR" for li in line_items)

    subtotal_myr = _sum_or_none(li["line_total_myr"] for li in line_items)

    total_wp = sum(
        (li["quantity"] or 0) * (li["rated_wp"] or 0)
        for li in line_items
        if li["category"] == "module" and li["quantity"] and li["rated_wp"]
    )
    module_value = sum(
        li["line_total_myr"]
        for li in line_items
        if li["category"] == "module" and li["line_total_myr"] is not None
    )
    blended_price_per_wp_myr = round(module_value / total_wp, 3) if total_wp else None
    tier1_line_count = sum(1 for li in line_items if li["bnef_tier1"] is True)
    flagged_line_count = sum(1 for li in line_items if li["flags"])

    if not line_items:
        parse_status = "failed"
        notes.append("No line items were extracted from the document.")
    elif all(
        li["manufacturer"] and li["model"] and li["quantity"] is not None and li["unit_price"] is not None
        for li in line_items
    ):
        parse_status = "parsed"
    else:
        parse_status = "partial"
        notes.append("Some line items are missing manufacturer, model, quantity, or price — reviewer should confirm.")

    return {
        "supplier_name_raw": supplier_name_raw,
        "source_filename": filename,
        "currency": top_currency,
        "fx_rate_to_myr": fx_rate if converted_any else 1.0,
        "parse_status": parse_status,
        "page_count": page_count,
        "subtotal_myr": subtotal_myr,
        "parse_notes": " ".join(notes),
        # Not part of the ARD §5.4 API response shape, but mirror the `supplier_quotes`
        # DB columns (ARD §3.3) so the caller can persist them without a second parse.
        "raw_text": raw_text,
        "raw_llm_json": raw_llm_json,
        "line_items": line_items,
        "summary": {
            "total_wp": total_wp,
            "blended_price_per_wp_myr": blended_price_per_wp_myr,
            "tier1_line_count": tier1_line_count,
            "flagged_line_count": flagged_line_count,
        },
    }


def _failed_result(filename: str, fx_rate: float, page_count: int, raw_text: str, raw_llm_json: dict | None) -> dict:
    return {
        "supplier_name_raw": Path(filename).stem,
        "source_filename": filename,
        "currency": "MYR",
        "fx_rate_to_myr": fx_rate,
        "parse_status": "failed",
        "page_count": page_count,
        "subtotal_myr": None,
        "parse_notes": "Vision model returned no usable data after one retry.",
        "raw_text": raw_text,
        "raw_llm_json": raw_llm_json,
        "line_items": [],
        "summary": {"total_wp": 0, "blended_price_per_wp_myr": None, "tier1_line_count": 0, "flagged_line_count": 0},
    }


# --------------------------------------------------------------------------
# Stub path — no LLM_API_KEY (same discipline as llm_client._stub_analyze_photo)
# --------------------------------------------------------------------------

_STUB_QUOTES = [
    {
        "supplier_name": "Demo Solar Supplies Sdn Bhd",
        "line_items": [
            {
                "manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M",
                "description": "550Wp N-type TOPCon monocrystalline module, black frame",
                "quantity": 20, "unit": "pcs", "unit_price": 467.0, "currency": "MYR",
                "wattage_wp": 550, "warranty_years": 25, "lead_time_days": 21,
            },
            {
                "manufacturer": "Huawei", "model": "SUN2000-10KTL-M1",
                "description": "10kW three-phase string inverter",
                "quantity": 1, "unit": "unit", "unit_price": 6800.0, "currency": "MYR",
                "wattage_wp": None, "warranty_years": 10, "lead_time_days": 14,
            },
        ],
    },
    {
        "supplier_name": "Northern Array Trading",
        "line_items": [
            {
                "manufacturer": "Jinko", "model": "Tiger Neo JKM575N-72HL4-BDV",
                "description": "575W Tiger Neo N-type module",
                "quantity": 24, "unit": "nos", "unit_price": 118.0, "currency": "USD",
                "wattage_wp": 575, "warranty_years": 25, "lead_time_days": 30,
            },
        ],
    },
]


def _stub_parse_quote(filename: str) -> dict:
    seed = sum(ord(c) for c in filename) or 1
    return _STUB_QUOTES[seed % len(_STUB_QUOTES)]


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

async def parse_quote(data: bytes, filename: str, fx_rate: float = DEFAULT_FX_RATE) -> dict:
    """Parse a supplier quote PDF or image into the normalised ARD §5.4 shape.

    Never raises — any failure (unreadable file, LLM error, malformed JSON after
    retry) is reported as `parse_status: "failed"` in the returned dict.
    """
    try:
        if pdf_extract.is_pdf(data):
            pages = pdf_extract.page_count(data)
            images = pdf_extract.render_pdf_pages(data)
            raw_text = pdf_extract.extract_pdf_text(data)
        else:
            pages = 1
            images = [pdf_extract.normalise_image(data)]
            raw_text = ""
    except Exception:
        logger.exception("quote_parser: could not read %r as PDF or image", filename)
        return _failed_result(filename, fx_rate, 0, "", None)

    if not settings.llm_api_key:
        raw_payload = _stub_parse_quote(filename)
        result = _finalise(raw_payload, filename, fx_rate, pages, raw_text, raw_payload)
        stub_note = "Stub parse — no LLM_API_KEY configured."
        result["parse_notes"] = f"{result['parse_notes']} {stub_note}".strip()
        return result

    try:
        raw_payload = await _extract_with_vision(images, raw_text)
    except Exception:
        logger.exception("quote_parser: vision extraction raised for %r", filename)
        raw_payload = None

    if raw_payload is None or not isinstance(raw_payload, dict):
        return _failed_result(filename, fx_rate, pages, raw_text, None)

    return _finalise(raw_payload, filename, fx_rate, pages, raw_text, raw_payload)
