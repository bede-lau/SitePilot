"""Tool implementations the orchestrator can call.

Each function takes the live DB session plus the caller's phone number (so
actions like procurement know who to reply to) and returns a JSON-serialisable
result. Read tools query the same data the portal exposes; action tools reuse the
existing inspection/procurement logic rather than duplicating it.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.procurement import start_procurement_request
from app.models.models import (
    ActivityLog,
    InspectionReport,
    InvoiceDraft,
    Project,
    PurchaseOrder,
    Vendor,
)
from app.services.events import broadcast

logger = logging.getLogger("fieldbot.tools")


def _money(value) -> float | None:
    return float(value) if value is not None else None


async def _find_project(db: AsyncSession, name_or_id) -> Project | None:
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        proj = await db.get(Project, int(name_or_id))
        if proj:
            return proj
    if isinstance(name_or_id, str):
        result = await db.execute(
            select(Project).where(Project.name.ilike(f"%{name_or_id}%")).limit(1)
        )
        return result.scalar_one_or_none()
    return None


async def list_projects(db: AsyncSession, from_number: str, status: str | None = None) -> list[dict]:
    query = select(Project)
    if status:
        query = query.where(Project.status == status)
    projects = (await db.execute(query)).scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "client_name": p.client_name,
            "site_location": p.site_location,
            "region": p.region,
            "phase": p.phase,
            "total_panels": p.total_panels,
            "contract_value": _money(p.contract_value),
            "status": p.status,
        }
        for p in projects
    ]


async def get_project(db: AsyncSession, from_number: str, project: str) -> dict:
    proj = await _find_project(db, project)
    if not proj:
        return {"error": f"No project matching '{project}'."}
    counts = {}
    for label, model in (("inspections", InspectionReport), ("invoices", InvoiceDraft), ("purchase_orders", PurchaseOrder)):
        counts[label] = (
            await db.execute(select(func.count()).select_from(model).where(model.project_id == proj.id))
        ).scalar_one()
    return {
        "id": proj.id,
        "name": proj.name,
        "client_name": proj.client_name,
        "site_location": proj.site_location,
        "region": proj.region,
        "phase": proj.phase,
        "total_panels": proj.total_panels,
        "contract_value": _money(proj.contract_value),
        "status": proj.status,
        **counts,
    }


async def list_inspections(db: AsyncSession, from_number: str, project: str | None = None) -> list[dict]:
    query = select(InspectionReport).order_by(InspectionReport.created_at.desc()).limit(20)
    if project:
        proj = await _find_project(db, project)
        if not proj:
            return [{"error": f"No project matching '{project}'."}]
        query = query.where(InspectionReport.project_id == proj.id)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "panels_detected": r.panels_detected,
            "panels_with_issues": r.panels_with_issues,
            "completion_pct": _money(r.completion_pct),
            "issues": r.issues,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def list_invoices(db: AsyncSession, from_number: str, project: str | None = None) -> list[dict]:
    query = select(InvoiceDraft).order_by(InvoiceDraft.created_at.desc()).limit(20)
    if project:
        proj = await _find_project(db, project)
        if not proj:
            return [{"error": f"No project matching '{project}'."}]
        query = query.where(InvoiceDraft.project_id == proj.id)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "invoice_number": r.invoice_number,
            "claim_percentage": _money(r.claim_percentage),
            "claim_amount_myr": _money(r.claim_amount_myr),
            "status": r.status,
        }
        for r in rows
    ]


async def list_purchase_orders(db: AsyncSession, from_number: str, project: str | None = None) -> list[dict]:
    query = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).limit(20)
    if project:
        proj = await _find_project(db, project)
        if not proj:
            return [{"error": f"No project matching '{project}'."}]
        query = query.where(PurchaseOrder.project_id == proj.id)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "po_number": r.po_number,
            "item_description": r.item_description,
            "quantity": r.quantity,
            "unit_price_myr": _money(r.unit_price_myr),
            "total_price_myr": _money(r.total_price_myr),
            "status": r.status,
        }
        for r in rows
    ]


async def find_vendors(db: AsyncSession, from_number: str, region: str | None = None) -> list[dict]:
    query = select(Vendor).where(Vendor.is_active == True)  # noqa: E712
    if region:
        query = query.where(Vendor.region == region)
    query = query.order_by(Vendor.on_time_rate.desc())
    vendors = (await db.execute(query)).scalars().all()
    return [
        {
            "id": v.id,
            "company_name": v.company_name,
            "region": v.region,
            "contact_email": v.contact_email,
            "on_time_rate": _money(v.on_time_rate),
            "unit_price_myr": _money(v.unit_price_myr),
            "specialization": v.specialization,
        }
        for v in vendors
    ]


async def start_procurement(
    db: AsyncSession, from_number: str, item_description: str, quantity: int, region: str | None = None
) -> dict:
    message = await start_procurement_request(db, from_number, item_description, quantity, region)
    return {"status": "rfq_started", "message_to_user": message}


async def draft_invoice(
    db: AsyncSession, from_number: str, project: str, claim_percentage: float
) -> dict:
    proj = await _find_project(db, project)
    if not proj:
        return {"error": f"No project matching '{project}'."}
    year = datetime.now(timezone.utc).year
    count = (await db.execute(select(func.count()).select_from(InvoiceDraft))).scalar_one()
    invoice_number = f"PC-{year}-{count + 1:03d}"
    claim_amount = round(float(proj.contract_value) * (claim_percentage / 100), 2)
    invoice = InvoiceDraft(
        project_id=proj.id,
        invoice_number=invoice_number,
        claim_percentage=claim_percentage,
        claim_amount_myr=claim_amount,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    log = ActivityLog(
        event_type="invoice_created",
        description=f"Invoice draft {invoice_number} created for {proj.name}",
        entity_type="invoice_draft",
        entity_id=invoice.id,
    )
    db.add(log)
    await db.commit()
    await broadcast("invoice_created", log.description, "invoice_draft", invoice.id)
    return {
        "invoice_number": invoice_number,
        "project": proj.name,
        "claim_percentage": claim_percentage,
        "claim_amount_myr": claim_amount,
    }


# name -> (callable, requires no extra wiring). The orchestrator dispatches on these.
TOOL_FUNCTIONS = {
    "list_projects": list_projects,
    "get_project": get_project,
    "list_inspections": list_inspections,
    "list_invoices": list_invoices,
    "list_purchase_orders": list_purchase_orders,
    "find_vendors": find_vendors,
    "start_procurement": start_procurement,
    "draft_invoice": draft_invoice,
}
