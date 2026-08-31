import base64
import json
import logging
import random
import re

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger("fieldbot.llm")

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        # DashScope's default (no timeout, 2 retries) means a single stalled request
        # can hang the whole chat turn for minutes. Cap it: 45s/request, one retry,
        # 10s to connect. A slow model is better surfaced as an error than an
        # indefinite spinner.
        _client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
            timeout=45.0,
            max_retries=1,
        )
    return _client


def get_client() -> AsyncOpenAI:
    """Public accessor for the orchestrator's tool-calling loop."""
    return _get_client()


def _parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)

REGION_HINTS = {
    "penang": "north",
    "bayan lepas": "north",
    "north": "north",
    "kl": "central",
    "kuala lumpur": "central",
    "cyberjaya": "central",
    "central": "central",
    "johor": "south",
    "south": "south",
}

VISION_SYSTEM_PROMPT = """You are a solar installation site inspector. Analyze this construction site photo and return a JSON object with these fields:

panels_detected (integer): number of solar panels visible that appear to be installed
panels_with_issues (integer): count of panels that look misaligned, damaged, or incorrectly positioned
issues (array of strings): brief description of each issue spotted, e.g. "Panel in row 3 appears tilted"
notes (string): any other observations about the installation state
If the image does not clearly show solar panels, return panels_detected: 0.
Return only valid JSON. No markdown, no explanation."""


def _stub_analyze_photo(image_bytes: bytes) -> dict:
    """Deterministic stand-in until a real vision model is wired in (LLM_API_KEY unset)."""
    seed = len(image_bytes) or 1
    rng = random.Random(seed)
    panels = rng.randint(25, 35)
    issues_n = rng.randint(0, 1)
    return {
        "panels_detected": panels,
        "panels_with_issues": issues_n,
        "issues": ["Panel in row 2 appears tilted"] if issues_n else [],
        "notes": "Stub analysis — no LLM_API_KEY configured.",
    }


async def analyze_photo(image_bytes: bytes) -> dict:
    if not settings.llm_api_key:
        return _stub_analyze_photo(image_bytes)

    data_uri = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
    response = await _get_client().chat.completions.create(
        model=settings.llm_vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_SYSTEM_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
    )
    text = response.choices[0].message.content or ""
    try:
        return _parse_json_response(text)
    except (json.JSONDecodeError, IndexError):
        logger.warning("vision LLM returned unparseable JSON: %r", text)
        return _stub_analyze_photo(image_bytes)


def _stub_extract_procurement_intent(message: str) -> dict:
    """Heuristic stand-in until a real text model is wired in (LLM_API_KEY unset)."""
    text = message.lower()

    qty_match = re.search(r"\b(\d+)\b", text)
    quantity = int(qty_match.group(1)) if qty_match else 1

    site_or_region = None
    for hint, region in REGION_HINTS.items():
        if hint in text:
            site_or_region = region
            break

    urgency = "urgent" if any(w in text for w in ("urgent", "asap", "immediately")) else "normal"

    return {
        "item_description": "solar panels",
        "quantity": quantity,
        "site_or_region": site_or_region,
        "urgency": urgency,
        "deadline_hint": None,
    }


PROCUREMENT_EXTRACT_PROMPT = """Extract procurement details from this message and return JSON:

item_description (string): what is being requested
quantity (integer): how many units, default 1 if unspecified
site_or_region (string): one of "north", "central", "south" based on any location mentioned \
(Penang/Bayan Lepas -> north, KL/Kuala Lumpur/Cyberjaya -> central, Johor -> south), or null if no location is mentioned
urgency (string): "urgent", "normal", or "low"
deadline_hint (string): any date/timeframe mentioned, or null

Message: "{message}"
Return only valid JSON. No markdown, no explanation."""


async def _chat_json(prompt: str) -> dict:
    response = await _get_client().chat.completions.create(
        model=settings.llm_text_model,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content or ""
    return _parse_json_response(text)


async def extract_procurement_intent(message: str) -> dict:
    if not settings.llm_api_key:
        return _stub_extract_procurement_intent(message)
    try:
        return await _chat_json(PROCUREMENT_EXTRACT_PROMPT.format(message=message))
    except (json.JSONDecodeError, IndexError):
        logger.warning("text LLM returned unparseable JSON for intent extraction")
        return _stub_extract_procurement_intent(message)


QUOTE_PARSE_PROMPT = """A solar materials vendor replied to a request-for-quote by email. \
Extract the quote from the email body below and return JSON:

declined (boolean): true if the vendor declined / cannot supply / is out of stock, otherwise false
unit_price_myr (number or null): price per unit in Malaysian Ringgit, null if not stated
delivery_days (integer or null): lead time in days, null if not stated
notes (string): one short sentence summarising the vendor's message

Email body:
\"\"\"
{body}
\"\"\"
Return only valid JSON. No markdown, no explanation."""


async def parse_quote_email(body: str) -> dict:
    """Turn a free-text vendor email reply into structured quote fields.

    Requires the text LLM — email replies are unstructured prose, so there is no
    sensible deterministic parser. Returns ``declined: True`` on failure so an
    unreadable reply doesn't get treated as a valid zero-price quote."""
    if not settings.llm_api_key:
        logger.warning("parse_quote_email called without LLM_API_KEY; cannot parse vendor reply")
        return {"declined": True, "unit_price_myr": None, "delivery_days": None, "notes": "LLM unavailable"}
    try:
        result = await _chat_json(QUOTE_PARSE_PROMPT.format(body=body[:4000]))
        price = result.get("unit_price_myr")
        result["unit_price_myr"] = round(float(price), 2) if price is not None else None
        days = result.get("delivery_days")
        result["delivery_days"] = int(days) if days is not None else None
        result["declined"] = bool(result.get("declined")) or result["unit_price_myr"] is None
        return result
    except (json.JSONDecodeError, IndexError, ValueError, TypeError):
        logger.warning("could not parse vendor quote email")
        return {"declined": True, "unit_price_myr": None, "delivery_days": None, "notes": "unparseable reply"}


async def generate_quote(vendor_name: str, item_description: str, quantity: int, base_unit_price: float, urgency: str) -> dict:
    if not settings.llm_api_key:
        variation = random.uniform(-0.05, 0.05)
        unit_price = round(base_unit_price * (1 + variation), 2)
        return {
            "vendor_name": vendor_name,
            "item_description": item_description,
            "quantity": quantity,
            "unit_price_myr": unit_price,
            "delivery_days": 3 if urgency == "urgent" else 5,
            "notes": "Stub quote — no LLM_API_KEY configured.",
        }

    prompt = f"""Generate a realistic supplier quote response as JSON:

vendor_name (string): use this vendor name exactly: {vendor_name}
item_description (string): {item_description}
quantity (integer): {quantity}
unit_price_myr (number): make it close to but slightly different from {base_unit_price}, realistic variation +/-5%
delivery_days (integer): 2-5 days depending on urgency {urgency}
notes (string): brief professional note from the vendor

Return only valid JSON. No markdown, no explanation."""
    try:
        quote = await _chat_json(prompt)
        quote.setdefault("vendor_name", vendor_name)
        quote.setdefault("item_description", item_description)
        quote.setdefault("quantity", quantity)
        delivery_match = re.search(r"\d+", str(quote.get("delivery_days", "")))
        quote["delivery_days"] = int(delivery_match.group()) if delivery_match else (3 if urgency == "urgent" else 5)
        quote["unit_price_myr"] = round(float(quote.get("unit_price_myr", base_unit_price)), 2)
        return quote
    except (json.JSONDecodeError, IndexError, ValueError, TypeError):
        logger.warning("text LLM returned unparseable JSON for quote generation")
        variation = random.uniform(-0.05, 0.05)
        unit_price = round(base_unit_price * (1 + variation), 2)
        return {
            "vendor_name": vendor_name,
            "item_description": item_description,
            "quantity": quantity,
            "unit_price_myr": unit_price,
            "delivery_days": 3 if urgency == "urgent" else 5,
            "notes": "Fallback quote — LLM response unparseable.",
        }
