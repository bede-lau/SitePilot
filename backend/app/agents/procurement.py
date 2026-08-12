import asyncio
import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.models import ActivityLog, ConversationSession, Project, PurchaseOrder, RFQ, Vendor
from app.services.email_client import send_email_with_attachment, send_rfq_email, subject_token
from app.services.events import broadcast
from app.services.llm_client import extract_procurement_intent, generate_quote
from app.services.messaging import send_document, send_message
from app.services.pdf import generate_po_pdf

logger = logging.getLogger("fieldbot.procurement")

QUOTE_DELAY_SECONDS = 8

# asyncio's event loop only holds a *weak* reference to tasks created via
# create_task — with nothing else referencing them, a task can be garbage
# collected mid-flight with no error logged. Keep a strong reference here for
# every fire-and-forget background task spawned from a request handler.
_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def _lookup_vendors(db: AsyncSession, region: str | None) -> list[Vendor]:
    query = select(Vendor).where(Vendor.is_active == True)  # noqa: E712
    if region:
        query = query.where(Vendor.region == region)
    query = query.order_by(Vendor.on_time_rate.desc())
    vendors = (await db.execute(query)).scalars().all()
    if not vendors and region:
        # fallback to all active vendors if region match is empty
        vendors = (
            (await db.execute(select(Vendor).where(Vendor.is_active == True).order_by(Vendor.on_time_rate.desc())))  # noqa: E712
            .scalars()
            .all()
        )
    return list(vendors)


async def _next_po_number(db: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    count = (await db.execute(select(func.count()).select_from(PurchaseOrder))).scalar_one()
    return f"PO-{year}-{count + 1:03d}"


async def run_procurement(from_number: str, body: str) -> None:
    """Kicked off as a background task so the webhook response isn't blocked by the quote delay."""
    async with AsyncSessionLocal() as db:
        intent = await extract_procurement_intent(body)
        region = intent.get("site_or_region")
        quantity = intent.get("quantity", 1)
        item_description = intent.get("item_description", "materials")
        urgency = intent.get("urgency", "normal")

        region_label = region or "all regions"
        send_message(from_number, f"Got it. Searching approved vendors for {region_label}… 🔍")

        vendors = await _lookup_vendors(db, region)
        if not vendors:
            send_message(from_number, "No approved vendors found. A team member will follow up.")
            return

        send_message(from_number, f"RFQ sent to {len(vendors)} vendors. Waiting for quotes…")

        await asyncio.sleep(QUOTE_DELAY_SECONDS)

        top_vendor = vendors[0]
        quote = await generate_quote(
            top_vendor.company_name, item_description, quantity, float(top_vendor.unit_price_myr or 0), urgency
        )

        unit_price = quote["unit_price_myr"]
        delivery_days = quote["delivery_days"]
        total = round(unit_price * quantity, 2)

        result = await db.execute(
            select(ConversationSession).where(ConversationSession.phone_number == from_number)
        )
        session = result.scalar_one_or_none()
        if session is None:
            session = ConversationSession(phone_number=from_number)
            db.add(session)

        project_id = (session.context or {}).get("project_id")
        if project_id is None:
            # Demo phone is the only one pre-seeded with a project; any other
            # sender falls back to the first active project so the PO write
            # doesn't violate the NOT NULL project_id FK.
            project_id = (
                await db.execute(select(Project.id).where(Project.status == "active").limit(1))
            ).scalar_one_or_none()

        session.state = "awaiting_procurement_confirm"
        session.context = {
            **(session.context or {}),
            "pending_po": {
                "vendor_id": top_vendor.id,
                "vendor_name": top_vendor.company_name,
                "item_description": item_description,
                "quantity": quantity,
                "unit_price_myr": unit_price,
                "total_price_myr": total,
                "delivery_days": delivery_days,
                "project_id": project_id,
            },
        }
        await db.commit()

        project = await db.get(Project, project_id) if project_id else None
        pdf_bytes = generate_po_pdf(project, session.context["pending_po"])
        send_document(from_number, pdf_bytes, "po_draft.pdf", caption="Draft PO for approval")

        reply = (
            "\U0001F4CB Best Quote Received\n\n"
            f"Vendor: {top_vendor.company_name}\n"
            f"Item: {item_description}\n"
            f"Qty: {quantity} units × RM {unit_price:.0f}\n"
            f"Total: RM {total:.0f}\n"
            f"Delivery: {delivery_days} days (on-time rate: {top_vendor.on_time_rate}%)\n\n"
            "Approve this PO? Reply YES to confirm."
        )
        send_message(from_number, reply)


async def _resolve_project_id(db: AsyncSession, from_number: str) -> int | None:
    result = await db.execute(
        select(ConversationSession).where(ConversationSession.phone_number == from_number)
    )
    session = result.scalar_one_or_none()
    project_id = (session.context or {}).get("project_id") if session else None
    if project_id is None:
        project_id = (
            await db.execute(select(Project.id).where(Project.status == "active").limit(1))
        ).scalar_one_or_none()
    return project_id


def _rfq_email_body(vendor_name: str, item_description: str, quantity: int, token: str) -> str:
    return (
        f"Dear {vendor_name},\n\n"
        "We would like to request a quotation for the following:\n\n"
        f"  Item: {item_description}\n"
        f"  Quantity: {quantity} units\n\n"
        "Please reply to this email with your unit price (MYR) and delivery lead time "
        "in days. Keep the subject line unchanged so we can match your quote.\n\n"
        "Regards,\nFieldBot Procurement (on behalf of the site manager)\n\n"
        f"Ref: {subject_token(token)}"
    )


async def start_procurement_request(
    db: AsyncSession, from_number: str, item_description: str, quantity: int, region: str | None
) -> str:
    """Orchestrator entrypoint. Sends real RFQ emails to matching vendors when email
    is configured; otherwise hands off to the simulated-quote background task so the
    demo still works without an inbox set up. Returns a short status line for the user."""
    vendors = await _lookup_vendors(db, region)
    if not vendors:
        return "I couldn't find any approved vendors for that request. A team member will follow up."

    if not settings.email_enabled:
        # No SMTP configured — keep the deterministic simulated flow (8s delay then a quote).
        _spawn(run_procurement(from_number, f"{quantity} {item_description} {region or ''}"))
        return f"Searching approved vendors for {region or 'all regions'} and requesting quotes… 🔍"

    project_id = await _resolve_project_id(db, from_number)
    batch_id = secrets.token_hex(4)
    sent_to = []
    for vendor in vendors:
        token = secrets.token_hex(5)
        rfq = RFQ(
            batch_id=batch_id,
            token=token,
            project_id=project_id,
            vendor_id=vendor.id,
            manager_phone=from_number,
            item_description=item_description,
            quantity=quantity,
        )
        db.add(rfq)
        try:
            await send_rfq_email(
                vendor.contact_email,
                f"RFQ: {quantity} x {item_description} {subject_token(token)}",
                _rfq_email_body(vendor.company_name, item_description, quantity, token),
            )
            sent_to.append(vendor.company_name)
        except Exception:  # noqa: BLE001
            logger.exception("failed to send RFQ to %s <%s>", vendor.company_name, vendor.contact_email)
            rfq.status = "expired"
    await db.commit()

    if not sent_to:
        return "I tried to email the vendors but the RFQ send failed. Check the SMTP settings."

    await broadcast("rfq_sent", f"RFQ sent to {len(sent_to)} vendors for {quantity} {item_description}", "rfq", None)
    # Real RFQ emails are sent (demonstrates the email integration) but these are demo
    # vendor inboxes that won't actually reply, so the agent reads the vendors' own
    # rate card straight out of the DB and narrates the comparison instead of waiting
    # on IMAP or calling an LLM for fake numbers.
    _spawn(simulate_vendor_quotes(batch_id, item_description, quantity))
    return (
        f"RFQ emailed to {len(sent_to)} vendor(s): {', '.join(sent_to)}. "
        "I'll message you here as soon as quotes come back. 📨"
    )


def _estimate_delivery_days(on_time_rate: float | None) -> int:
    rate = float(on_time_rate or 0)
    if rate >= 95:
        return 3
    if rate >= 85:
        return 5
    return 7


async def simulate_vendor_quotes(batch_id: str, item_description: str, quantity: int) -> None:
    """Demo-mode quote retrieval: every vendor already has a unit_price_myr and
    on_time_rate seeded in the DB, so the quote *is* a plain query — no LLM call,
    no waiting on a reply that will never come. Narrates the comparison/selection
    reasoning in chat, then hands off to _finalize_batch's approval flow."""
    await asyncio.sleep(min(QUOTE_DELAY_SECONDS, 3))
    async with AsyncSessionLocal() as db:
        rfqs = (await db.execute(select(RFQ).where(RFQ.batch_id == batch_id, RFQ.status == "sent"))).scalars().all()
        if not rfqs:
            return
        manager_phone = rfqs[0].manager_phone

        send_message(manager_phone, "🔍 Querying vendor database for rates and reliability…")

        quotes = []
        for rfq in rfqs:
            vendor = await db.get(Vendor, rfq.vendor_id)
            if vendor is None:
                continue
            unit_price = float(vendor.unit_price_myr or 0)
            delivery_days = _estimate_delivery_days(vendor.on_time_rate)
            total = round(unit_price * quantity, 2)
            rfq.status = "quoted"
            rfq.quote_unit_price_myr = unit_price
            rfq.quote_delivery_days = delivery_days
            rfq.quoted_at = datetime.now(timezone.utc)
            quotes.append((vendor, unit_price, delivery_days, total))
        await db.commit()

        if not quotes:
            send_message(manager_phone, "No vendors were able to quote that request. A team member will follow up.")
            return

        lines = [f"\U0001F4CA Quotes from {len(quotes)} vendor(s) for {quantity} x {item_description}:\n"]
        for vendor, unit_price, delivery_days, total in quotes:
            lines.append(
                f"• {vendor.company_name}: RM {unit_price:.0f}/unit × {quantity} = RM {total:,.0f} "
                f"({delivery_days}d delivery, {vendor.on_time_rate}% on-time)"
            )

        reliable = [q for q in quotes if float(q[0].on_time_rate or 0) >= 85]
        pool = reliable if reliable else quotes
        best = min(pool, key=lambda q: q[3])
        lines.append("")
        if reliable:
            lines.append(
                f"\U0001F9E0 Reasoning: comparing total cost among vendors with ≥85% on-time delivery "
                f"→ lowest is {best[0].company_name} at RM {best[3]:,.0f}."
            )
        else:
            lines.append(
                f"\U0001F9E0 Reasoning: no vendor cleared the 85% on-time bar — picking lowest total cost "
                f"→ {best[0].company_name} at RM {best[3]:,.0f}."
            )
        send_message(manager_phone, "\n".join(lines))

        await _finalize_batch(db, batch_id)


async def start_po_request(db: AsyncSession, session: ConversationSession, from_number: str, body: str) -> None:
    """Deterministic follow-up after an inspection: the manager already said
    "po", this turn's free text is the item/quantity. Reuses the same intent
    extraction + RFQ flow as the orchestrator's start_procurement tool."""
    intent = await extract_procurement_intent(body)
    item_description = intent.get("item_description", "materials")
    quantity = intent.get("quantity", 1)
    region = intent.get("site_or_region")

    session.state = "idle"
    await db.commit()

    message = await start_procurement_request(db, from_number, item_description, quantity, region)
    send_message(from_number, message)


async def _batch_is_ready(db: AsyncSession, batch_id: str) -> bool:
    """True once every RFQ in the batch has a terminal status (no longer 'sent')."""
    pending = (
        await db.execute(select(func.count()).select_from(RFQ).where(RFQ.batch_id == batch_id, RFQ.status == "sent"))
    ).scalar_one()
    return pending == 0


async def _finalize_batch(db: AsyncSession, batch_id: str) -> None:
    """Pick the cheapest quoted RFQ in a finished batch and present one PO draft.
    If every vendor declined/expired with no quote, tell the manager and stop."""
    quoted = (
        await db.execute(
            select(RFQ)
            .where(RFQ.batch_id == batch_id, RFQ.status == "quoted")
            .order_by(RFQ.quote_unit_price_myr.asc())
        )
    ).scalars().all()

    any_rfq = (await db.execute(select(RFQ).where(RFQ.batch_id == batch_id).limit(1))).scalar_one_or_none()
    if any_rfq is None:
        return
    manager_phone = any_rfq.manager_phone

    if not quoted:
        send_message(manager_phone, "No vendors were able to quote that request. A team member will follow up.")
        return

    best = quoted[0]
    best_vendor = await db.get(Vendor, best.vendor_id)
    unit_price = float(best.quote_unit_price_myr)
    total = round(unit_price * best.quantity, 2)

    session = (
        await db.execute(select(ConversationSession).where(ConversationSession.phone_number == manager_phone))
    ).scalar_one_or_none()
    if session is None:
        session = ConversationSession(phone_number=manager_phone)
        db.add(session)
    session.state = "awaiting_procurement_confirm"
    session.context = {
        **(session.context or {}),
        "pending_po": {
            "vendor_id": best.vendor_id,
            "vendor_name": best_vendor.company_name if best_vendor else "Vendor",
            "item_description": best.item_description,
            "quantity": best.quantity,
            "unit_price_myr": unit_price,
            "total_price_myr": total,
            "delivery_days": best.quote_delivery_days,
            "project_id": best.project_id,
            "rfq_batch_id": batch_id,
        },
    }
    await db.commit()

    await broadcast(
        "quote_received", f"Best quote selected from {best_vendor.company_name if best_vendor else 'vendor'}", "rfq", best.id
    )

    project = await db.get(Project, best.project_id) if best.project_id else None
    pdf_bytes = generate_po_pdf(project, session.context["pending_po"])
    send_document(manager_phone, pdf_bytes, "po_draft.pdf", caption="Draft PO for approval")

    reply = (
        "\U0001F4CB Best Quote Received\n\n"
        f"Vendor: {best_vendor.company_name if best_vendor else 'Vendor'}\n"
        f"Item: {best.item_description}\n"
        f"Qty: {best.quantity} units × RM {unit_price:.0f}\n"
        f"Total: RM {total:.0f}\n"
        f"Delivery: {best.quote_delivery_days} days "
        f"(on-time rate: {best_vendor.on_time_rate if best_vendor else 'n/a'}%)\n"
        f"({len(quoted)} vendor(s) quoted)\n\n"
        "Approve this PO? Reply YES to confirm."
    )
    send_message(manager_phone, reply)


async def process_quote_reply(token: str, parsed: dict) -> None:
    """Called by the inbound email poller for each tagged vendor reply.

    Only records the quote against its RFQ row. The PO draft is presented once,
    by _finalize_batch, after every vendor in the batch has responded (or the
    batch times out — see check_stale_batches)."""
    async with AsyncSessionLocal() as db:
        rfq = (await db.execute(select(RFQ).where(RFQ.token == token))).scalar_one_or_none()
        if rfq is None:
            logger.warning("quote reply for unknown token=%s", token)
            return
        if rfq.status != "sent":
            return  # already processed this reply

        vendor = await db.get(Vendor, rfq.vendor_id)
        if parsed.get("declined") or parsed.get("unit_price_myr") is None:
            rfq.status = "declined"
            rfq.quote_notes = parsed.get("notes")
        else:
            rfq.status = "quoted"
            rfq.quote_unit_price_myr = parsed["unit_price_myr"]
            rfq.quote_delivery_days = parsed.get("delivery_days") or 5
            rfq.quote_notes = parsed.get("notes")
            rfq.quoted_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("RFQ %s -> %s (vendor=%s)", token, rfq.status, vendor.company_name if vendor else "?")

        if await _batch_is_ready(db, rfq.batch_id):
            await _finalize_batch(db, rfq.batch_id)


async def check_stale_batches() -> None:
    """Finalize any batch that has outstanding (status='sent') RFQs older than the
    timeout, so a non-responding vendor doesn't block the decision forever."""
    cutoff = datetime.now(timezone.utc).timestamp() - settings.rfq_batch_timeout_seconds
    async with AsyncSessionLocal() as db:
        stale = (await db.execute(select(RFQ).where(RFQ.status == "sent"))).scalars().all()
        stale_batches = {
            r.batch_id for r in stale if r.created_at and r.created_at.replace(tzinfo=timezone.utc).timestamp() < cutoff
        }
        if not stale_batches:
            return
        from sqlalchemy import update as sql_update

        for batch_id in stale_batches:
            await db.execute(
                sql_update(RFQ).where(RFQ.batch_id == batch_id, RFQ.status == "sent").values(status="expired")
            )
            await db.commit()
            logger.info("RFQ batch %s timed out; finalizing with quotes received so far", batch_id)
            await _finalize_batch(db, batch_id)


async def confirm_purchase_order(db: AsyncSession, session: ConversationSession, from_number: str) -> None:
    pending = (session.context or {}).get("pending_po")
    if not pending:
        send_message(from_number, "No pending order to confirm.")
        return

    project_id = pending.get("project_id")
    po_number = await _next_po_number(db)
    po = PurchaseOrder(
        project_id=project_id,
        vendor_id=pending["vendor_id"],
        po_number=po_number,
        item_description=pending["item_description"],
        quantity=pending["quantity"],
        unit_price_myr=pending["unit_price_myr"],
        total_price_myr=pending["total_price_myr"],
        status="sent",
    )
    db.add(po)

    project = await db.get(Project, project_id) if project_id else None
    if project:
        project.budget_used_myr = float(project.budget_used_myr or 0) + float(pending["total_price_myr"])

    await db.commit()
    await db.refresh(po)

    log = ActivityLog(
        event_type="po_created",
        description=f"{po_number} created for {pending['vendor_name']}",
        entity_type="purchase_order",
        entity_id=po.id,
    )
    db.add(log)

    batch_id = pending.get("rfq_batch_id")
    if batch_id:
        from sqlalchemy import update as sql_update

        await db.execute(
            sql_update(RFQ)
            .where(RFQ.batch_id == batch_id, RFQ.status.in_(["sent", "quoted"]))
            .values(status="expired")
        )

    session.state = "idle"
    session.context = {k: v for k, v in (session.context or {}).items() if k != "pending_po"}
    await db.commit()

    await broadcast("po_created", log.description, "purchase_order", po.id)

    vendor = await db.get(Vendor, pending["vendor_id"])
    pdf_bytes = generate_po_pdf(project, {**pending, "po_number": po_number})

    if settings.email_enabled and vendor:
        try:
            await send_email_with_attachment(
                vendor.contact_email,
                f"Purchase Order {po_number} — {pending['item_description']}",
                f"Please find attached {po_number} for {pending['quantity']} x {pending['item_description']} "
                f"(RM {float(pending['total_price_myr']):,.2f}). Expected delivery: {pending['delivery_days']} days.",
                pdf_bytes,
                f"{po_number}.pdf",
            )
        except Exception:  # noqa: BLE001
            logger.exception("PO email failed for po=%s vendor=%s", po.id, vendor.contact_email)
    else:
        logger.info("[email:stub] %s would email vendor=%s", po_number, pending["vendor_name"])

    send_document(from_number, pdf_bytes, f"{po_number}.pdf", caption=f"{po_number} — approved")
    reply = (
        f"✅ {po_number} Created\n\n"
        f"{pending['vendor_name']} has been notified.\n"
        f"Expected delivery: in {pending['delivery_days']} days\n\n"
        f"View PO → {settings.frontend_base_url}/purchase-orders/{po.id}"
    )
    send_message(from_number, reply)


async def cancel_purchase_order(db: AsyncSession, session: ConversationSession, from_number: str) -> None:
    session.state = "idle"
    session.context = {k: v for k, v in (session.context or {}).items() if k != "pending_po"}
    await db.commit()
    send_message(from_number, "OK, cancelled.")
