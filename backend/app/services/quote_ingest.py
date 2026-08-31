"""Shared quote-parsing + persistence logic used by both routes/quotes.py
(dashboard drag-and-drop) and agents/tools.py's parse_supplier_quote tool
(chat-driven), so the two entry points can't drift.

Delegates extraction to Agent B's app.agents.quote_parser.parse_quote —
imported lazily so this module (and anything that imports it) still loads
before that file lands."""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.models import ActivityLog, QuoteLineItem, SupplierQuote, Vendor
from app.routes.uploads import resolve_upload_path
from app.services.events import broadcast

logger = logging.getLogger("fieldbot.quote_ingest")


class QuoteIngestError(Exception):
    """Raised for caller-facing failures (missing file, parser not landed)."""


async def _match_vendor(db: AsyncSession, supplier_name_raw: str | None) -> Vendor | None:
    if not supplier_name_raw or not supplier_name_raw.strip():
        return None
    name_lower = supplier_name_raw.strip().lower()
    vendors = (await db.execute(select(Vendor))).scalars().all()
    for v in vendors:
        vendor_lower = v.company_name.lower()
        if vendor_lower in name_lower or name_lower in vendor_lower:
            return v
    return None


def _backfill_bnef(line: dict) -> dict:
    if line.get("bnef_tier1") is not None or not line.get("manufacturer"):
        return line
    try:
        from app.data.bnef import match_manufacturer  # Agent A — lazy import
    except ImportError:
        return line
    try:
        is_tier1, matched_name = match_manufacturer(line["manufacturer"])
        line["bnef_tier1"] = bool(is_tier1)
        line["tier_match_name"] = matched_name
    except Exception:  # noqa: BLE001
        logger.exception("bnef match failed for manufacturer=%r", line.get("manufacturer"))
    return line


async def ingest_quote(db: AsyncSession, file_id: str, project_id: int | None = None) -> SupplierQuote:
    """Resolve an uploaded file by id, parse it, match it to a vendor, and
    persist SupplierQuote + QuoteLineItem rows. Raises QuoteIngestError for
    caller-facing problems (missing file / parser not available)."""
    path = resolve_upload_path(file_id)
    if path is None:
        raise QuoteIngestError(f"No uploaded file with id {file_id}")

    try:
        from app.agents.quote_parser import parse_quote  # Agent B — lazy import
    except ImportError as exc:
        raise QuoteIngestError("Quote parser not available yet (app.agents.quote_parser not landed)") from exc

    data = path.read_bytes()
    parsed = await parse_quote(data, path.name, fx_rate=settings.usd_myr_rate)

    vendor = await _match_vendor(db, parsed.get("supplier_name_raw"))

    quote = SupplierQuote(
        project_id=project_id,
        vendor_id=vendor.id if vendor else None,
        supplier_name_raw=parsed.get("supplier_name_raw"),
        source_filename=parsed.get("source_filename") or path.name,
        source_url=f"/static/uploads/quotes/{path.name}",
        currency=parsed.get("currency", "MYR"),
        fx_rate_to_myr=parsed.get("fx_rate_to_myr", 1.0),
        page_count=parsed.get("page_count"),
        parse_status=parsed.get("parse_status", "parsed"),
        parse_notes=parsed.get("parse_notes"),
        raw_llm_json=parsed,
        subtotal_myr=parsed.get("subtotal_myr"),
    )
    db.add(quote)
    await db.flush()

    for i, line in enumerate(parsed.get("line_items", []), start=1):
        line = _backfill_bnef(dict(line))
        db.add(
            QuoteLineItem(
                quote_id=quote.id,
                line_no=line.get("line_no", i),
                category=line.get("category", "unknown"),
                manufacturer=line.get("manufacturer"),
                model=line.get("model"),
                description=line.get("description"),
                quantity=line.get("quantity"),
                unit=line.get("unit"),
                unit_price=line.get("unit_price"),
                currency=line.get("currency"),
                unit_price_myr=line.get("unit_price_myr"),
                line_total_myr=line.get("line_total_myr"),
                rated_wp=line.get("rated_wp"),
                price_per_wp_myr=line.get("price_per_wp_myr"),
                warranty_years=line.get("warranty_years"),
                lead_time_days=line.get("lead_time_days"),
                bnef_tier1=line.get("bnef_tier1"),
                tier_match_name=line.get("tier_match_name"),
                flags=line.get("flags", []),
            )
        )

    await db.commit()
    await db.refresh(quote, attribute_names=["line_items"])

    log = ActivityLog(
        event_type="quote_parsed",
        description=f"Parsed quote from {quote.supplier_name_raw or path.name}",
        entity_type="supplier_quote",
        entity_id=quote.id,
    )
    db.add(log)
    await db.commit()
    await broadcast("quote_parsed", log.description, "supplier_quote", quote.id)

    return quote


def serialize_quote(quote: SupplierQuote) -> dict:
    line_items = [
        {
            "line_no": li.line_no,
            "category": li.category,
            "manufacturer": li.manufacturer,
            "model": li.model,
            "description": li.description,
            "quantity": float(li.quantity) if li.quantity is not None else None,
            "unit": li.unit,
            "unit_price": float(li.unit_price) if li.unit_price is not None else None,
            "currency": li.currency,
            "unit_price_myr": float(li.unit_price_myr) if li.unit_price_myr is not None else None,
            "line_total_myr": float(li.line_total_myr) if li.line_total_myr is not None else None,
            "rated_wp": float(li.rated_wp) if li.rated_wp is not None else None,
            "price_per_wp_myr": float(li.price_per_wp_myr) if li.price_per_wp_myr is not None else None,
            "warranty_years": li.warranty_years,
            "lead_time_days": li.lead_time_days,
            "bnef_tier1": li.bnef_tier1,
            "tier_match_name": li.tier_match_name,
            "flags": li.flags,
        }
        for li in sorted(quote.line_items, key=lambda x: x.line_no)
    ]
    total_wp = sum((li.get("rated_wp") or 0) * (li.get("quantity") or 0) for li in line_items if li.get("category") == "module")
    priced = [li for li in line_items if li.get("price_per_wp_myr")]
    blended = round(sum(li["price_per_wp_myr"] for li in priced) / len(priced), 4) if priced else None
    return {
        "id": quote.id,
        "project_id": quote.project_id,
        "vendor_id": quote.vendor_id,
        "vendor_matched": quote.vendor_id is not None,
        "supplier_name_raw": quote.supplier_name_raw,
        "source_filename": quote.source_filename,
        "source_url": quote.source_url,
        "currency": quote.currency,
        "fx_rate_to_myr": float(quote.fx_rate_to_myr),
        "page_count": quote.page_count,
        "parse_status": quote.parse_status,
        "parse_notes": quote.parse_notes,
        "subtotal_myr": float(quote.subtotal_myr) if quote.subtotal_myr is not None else None,
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
        "line_items": line_items,
        "summary": {
            "total_wp": total_wp,
            "blended_price_per_wp_myr": blended,
            "tier1_line_count": len([li for li in line_items if li.get("bnef_tier1")]),
            "flagged_line_count": len([li for li in line_items if li.get("flags")]),
        },
    }
