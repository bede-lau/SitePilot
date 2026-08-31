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


async def _find_vendor(db: AsyncSession, name_or_id) -> Vendor | None:
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and str(name_or_id).isdigit()):
        vendor = await db.get(Vendor, int(name_or_id))
        if vendor:
            return vendor
    if isinstance(name_or_id, str):
        result = await db.execute(
            select(Vendor).where(Vendor.company_name.ilike(f"%{name_or_id}%")).limit(1)
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


# ============================================================================
# ARD §5.6 — feasibility/procurement/catalog tools. These return
# (result_dict, card_or_none) — card_or_none is either a single
# {"card_type", "data"} dict, a list of them, or None. run_orchestrator (the
# Telegram path) only looks at the result_dict half; run_orchestrator_stream
# (the dashboard SSE path) also emits the card(s) so the UI paints the rich
# component immediately (ARD §5.5/§5.6). Each delegates to a shared
# app/services/*_engine.py module also used by the equivalent REST route, so
# the chat tool and the dashboard button can't drift.
# ============================================================================


async def parse_supplier_quote(db: AsyncSession, from_number: str, file_id: str, project: str | None = None) -> tuple[dict, dict]:
    from app.services.quote_ingest import QuoteIngestError, ingest_quote, serialize_quote

    project_id = None
    if project:
        proj = await _find_project(db, project)
        project_id = proj.id if proj else None
    try:
        quote = await ingest_quote(db, file_id, project_id)
    except QuoteIngestError as exc:
        return {"error": str(exc)}, None
    data = serialize_quote(quote)
    return data, {"card_type": "quote_parsed", "data": data}


async def run_feasibility(
    db: AsyncSession,
    from_number: str,
    project: str,
    panel_count: int | None = None,
    module: dict | None = None,
    inverter: dict | None = None,
    quote_id: int | None = None,
    system_type: str | None = None,
) -> tuple[dict, list[dict]]:
    from app.services.feasibility_engine import FeasibilityError, run_feasibility_for_project

    proj = await _find_project(db, project)
    if not proj:
        return {"error": f"No project matching '{project}'."}, None
    try:
        run = await run_feasibility_for_project(
            db,
            project_id=proj.id,
            system_type=system_type,
            panel_count=panel_count,
            module=module,
            inverter=inverter,
            quote_id=quote_id,
        )
    except FeasibilityError as exc:
        return {"error": str(exc)}, None
    data = run.results
    cards = [{"card_type": "feasibility", "data": data}]
    if data.get("confidence"):
        cards.append({"card_type": "confidence", "data": data["confidence"]})
    return data, cards


async def _resolve_feasibility_run(db: AsyncSession, feasibility_run_id: int | None, project: str | None):
    """Shared lookup for the ARD §5.6 tools that act on a prior feasibility run.

    Integration finding (E.3 live pass): the chat session history replays only the flattened
    reply text between turns, never the raw tool-result JSON (see agents/orchestrator.py's
    MAX_HISTORY_TURNS comment) — and ARD §5.6 explicitly forbids repeating numbers like a run id
    in that text. So on a follow-up turn ("approve and generate the PO for that") the model has no
    real feasibility_run_id in context. Observed live: it fabricated one (127) rather than asking,
    and called the real PO-generating tool with it — it 404'd harmlessly only because run ids were
    still low. financial_analysis already had the fix (fall back to the project's latest run); this
    gives generate_bos_spec and generate_po_package the same fallback so the model can pass
    `project` instead of guessing an id it was never given.
    """
    from app.models.models import FeasibilityRun

    if feasibility_run_id:
        run = await db.get(FeasibilityRun, feasibility_run_id)
        if not run:
            return None, {"error": f"No feasibility run with id {feasibility_run_id}"}
        return run, None
    if project:
        proj = await _find_project(db, project)
        if not proj:
            return None, {"error": f"No project matching '{project}'."}
        run = (
            await db.execute(
                select(FeasibilityRun)
                .where(FeasibilityRun.project_id == proj.id)
                .order_by(FeasibilityRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not run:
            return None, {"error": f"No feasibility run yet for '{proj.name}' — run one first."}
        return run, None
    return None, {"error": "Provide either feasibility_run_id or project."}


async def generate_bos_spec(
    db: AsyncSession, from_number: str, feasibility_run_id: int | None = None, project: str | None = None
) -> tuple[dict, dict | None]:
    run, error = await _resolve_feasibility_run(db, feasibility_run_id, project)
    if error:
        return error, None
    bos = (run.results or {}).get("bos", {})
    return bos, {"card_type": "bos_spec", "data": bos}


async def financial_analysis(
    db: AsyncSession,
    from_number: str,
    project: str | None = None,
    feasibility_run_id: int | None = None,
    system_cost_myr: float | None = None,
) -> tuple[dict, dict | None]:
    from app.models.models import FeasibilityRun
    from app.services.feasibility_engine import FeasibilityError, run_feasibility_for_project

    run = None
    if feasibility_run_id:
        run = await db.get(FeasibilityRun, feasibility_run_id)
        if not run:
            return {"error": f"No feasibility run with id {feasibility_run_id}"}, None
    elif project:
        proj = await _find_project(db, project)
        if not proj:
            return {"error": f"No project matching '{project}'."}, None
        latest = (
            await db.execute(
                select(FeasibilityRun)
                .where(FeasibilityRun.project_id == proj.id)
                .order_by(FeasibilityRun.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest and system_cost_myr is None:
            run = latest
        else:
            try:
                run = await run_feasibility_for_project(db, project_id=proj.id, system_cost_myr=system_cost_myr)
            except FeasibilityError as exc:
                return {"error": str(exc)}, None
    else:
        return {"error": "Provide either project or feasibility_run_id."}, None

    financial = (run.results or {}).get("financial", {})
    return financial, {"card_type": "financial", "data": financial}


async def list_components(
    db: AsyncSession, from_number: str, kind: str, brand: str | None = None, q: str | None = None
) -> tuple[dict, dict | None]:
    from app.models.models import Component

    query = select(Component).where(Component.kind == kind)
    if brand:
        query = query.where(Component.manufacturer.ilike(f"%{brand}%"))
    if q:
        query = query.where(Component.model.ilike(f"%{q}%"))
    rows = (await db.execute(query.limit(20))).scalars().all()
    items = [
        {
            "id": c.id, "manufacturer": c.manufacturer, "model": c.model, "tier": c.tier,
            "rated_wp": _money(c.rated_wp), "ac_rating_kw": _money(c.ac_rating_kw),
        }
        for c in rows
    ]
    data = {"kind": kind, "items": items}
    return data, {"card_type": "component_pick", "data": data}


async def check_bnef_tier(db: AsyncSession, from_number: str, manufacturer: str) -> tuple[dict, None]:
    try:
        from app.data.bnef import match_manufacturer  # Agent A — lazy import
    except ImportError:
        return {"manufacturer": manufacturer, "tier1": False, "matched_name": None, "source": "unavailable"}, None
    is_tier1, matched_name = match_manufacturer(manufacturer)
    return {
        "manufacturer": manufacturer, "tier1": bool(is_tier1), "matched_name": matched_name, "source": "bnef_registry",
    }, None


async def generate_po_package(
    db: AsyncSession,
    from_number: str,
    feasibility_run_id: int | None = None,
    project: str | None = None,
    vendor: str | None = None,
) -> tuple[dict, dict | None]:
    from app.services.po_engine import PoGenerateError, generate_po

    run, error = await _resolve_feasibility_run(db, feasibility_run_id, project)
    if error:
        return error, None

    vendor_id = None
    if vendor:
        v = await _find_vendor(db, vendor)
        vendor_id = v.id if v else None
    try:
        result = await generate_po(db, feasibility_run_id=run.id, vendor_id=vendor_id, notify_telegram=True)
    except PoGenerateError as exc:
        return {"error": str(exc)}, None
    return result, {"card_type": "po_draft", "data": result}


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
    "parse_supplier_quote": parse_supplier_quote,
    "run_feasibility": run_feasibility,
    "generate_bos_spec": generate_bos_spec,
    "financial_analysis": financial_analysis,
    "list_components": list_components,
    "check_bnef_tier": check_bnef_tier,
    "generate_po_package": generate_po_package,
}
