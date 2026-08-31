"""Shared PO-generation logic used by routes/po.py (dashboard "Approve &
Generate PO" button) and agents/tools.py's generate_po_package tool (chat).
Reuses the existing services/pdf.py + services/messaging.py rather than
reimplementing PDF/Telegram delivery."""
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.models import ActivityLog, FeasibilityRun, Project, PurchaseOrder, SupplierQuote, Vendor
from app.services.events import broadcast
from app.services.messaging import send_document
from app.services.pdf import generate_po_pdf

logger = logging.getLogger("fieldbot.po_engine")


class PoGenerateError(Exception):
    pass


async def _next_po_number(db: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    count = (await db.execute(select(func.count()).select_from(PurchaseOrder))).scalar_one()
    return f"PO-{year}-{count + 1:03d}"


async def _resolve_vendor(db: AsyncSession, run: FeasibilityRun, vendor_id: int | None) -> Vendor | None:
    if vendor_id:
        return await db.get(Vendor, vendor_id)
    if run.quote_id:
        quote = await db.get(SupplierQuote, run.quote_id)
        if quote and quote.vendor_id:
            return await db.get(Vendor, quote.vendor_id)
    return None


def _describe_system(results: dict) -> str:
    array = results.get("array") or {}
    module = array.get("module") or {}
    inverter = results.get("inverter") or {}
    parts = [f"{array.get('panel_count', '?')}x {module.get('manufacturer', '')} {module.get('model', '')}".strip()]
    if inverter:
        parts.append(f"+ {inverter.get('manufacturer', '')} {inverter.get('model', '')}".strip())
    return "Solar PV system — " + " ".join(p for p in parts if p)


async def generate_po(
    db: AsyncSession, *, feasibility_run_id: int, vendor_id: int | None = None, notify_telegram: bool = True
) -> dict:
    run = await db.get(FeasibilityRun, feasibility_run_id)
    if not run:
        raise PoGenerateError(f"No feasibility run with id {feasibility_run_id}")

    project = await db.get(Project, run.project_id)
    results = run.results or {}
    array = results.get("array") or {}
    financial = results.get("financial") or {}

    vendor = await _resolve_vendor(db, run, vendor_id)

    quantity = array.get("panel_count") or 1
    total_price_myr = financial.get("system_cost_myr")
    unit_price_myr = round(total_price_myr / quantity, 2) if total_price_myr and quantity else None
    item_description = _describe_system(results)

    po_number = await _next_po_number(db)
    po = PurchaseOrder(
        project_id=run.project_id,
        vendor_id=vendor.id if vendor else None,
        po_number=po_number,
        item_description=item_description,
        quantity=quantity,
        unit_price_myr=unit_price_myr,
        total_price_myr=total_price_myr,
        status="sent" if vendor else "draft",
    )
    db.add(po)

    if project and total_price_myr:
        project.budget_used_myr = float(project.budget_used_myr or 0) + float(total_price_myr)

    await db.commit()
    await db.refresh(po)

    log = ActivityLog(
        event_type="po_created",
        description=f"{po_number} created from feasibility run #{run.id}",
        entity_type="purchase_order",
        entity_id=po.id,
    )
    db.add(log)
    await db.commit()
    await broadcast("po_created", log.description, "purchase_order", po.id)

    pdf_details = {
        "po_number": po_number,
        "vendor_name": vendor.company_name if vendor else "TBD",
        "item_description": item_description,
        "quantity": quantity,
        "unit_price_myr": unit_price_myr or 0,
        "total_price_myr": total_price_myr or 0,
        "delivery_days": "-",
    }
    pdf_bytes = generate_po_pdf(project, pdf_details)

    pdf_dir = Path("uploads") / "pos"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    (pdf_dir / f"{po_number}.pdf").write_bytes(pdf_bytes)
    pdf_url = f"/static/uploads/pos/{po_number}.pdf"

    telegram_sent = False
    if notify_telegram:
        telegram_sent = send_document(
            settings.demo_phone_number,
            pdf_bytes,
            f"{po_number}.pdf",
            caption=f"{po_number} — generated from feasibility run #{run.id}",
        )

    return {
        "po": {
            "id": po.id, "project_id": po.project_id, "vendor_id": po.vendor_id,
            "po_number": po.po_number, "item_description": po.item_description,
            "quantity": po.quantity,
            "unit_price_myr": float(po.unit_price_myr) if po.unit_price_myr is not None else None,
            "total_price_myr": float(po.total_price_myr) if po.total_price_myr is not None else None,
            "status": po.status,
        },
        "pdf_url": pdf_url,
        "telegram_sent": telegram_sent,
    }
