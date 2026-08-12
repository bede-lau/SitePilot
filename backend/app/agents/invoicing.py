"""Invoice drafting + customer approval loop, triggered after a site inspection
(or ad hoc via the orchestrator's draft_invoice tool — see agents/tools.py).

The invoice row is written to the DB as soon as it's drafted (status='draft'),
same as before, so it's visible in the portal immediately. Approval only gates
the customer-facing email send."""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.models import ActivityLog, ConversationSession, InspectionReport, InvoiceDraft, Project
from app.services.email_client import send_email_with_attachment
from app.services.events import broadcast
from app.services.messaging import send_document, send_message
from app.services.pdf import generate_invoice_pdf

logger = logging.getLogger("fieldbot.invoicing")


async def _next_invoice_number(db: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    count = (await db.execute(select(func.count()).select_from(InvoiceDraft))).scalar_one()
    return f"PC-{year}-{count + 1:03d}"


async def start_invoice_draft(db: AsyncSession, session: ConversationSession, from_number: str) -> None:
    project_id = (session.context or {}).get("project_id")
    inspection_id = (session.context or {}).get("last_inspection_id")
    if not project_id or not inspection_id:
        send_message(from_number, "I don't have a recent inspection to base an invoice on. Send site photos first.")
        return

    project = await db.get(Project, project_id)
    inspection = await db.get(InspectionReport, inspection_id)
    if not project or not inspection:
        send_message(from_number, "Couldn't find that project or inspection anymore.")
        return

    claim_amount = round(float(project.contract_value) * (float(inspection.completion_pct or 0) / 100), 2)
    invoice_number = await _next_invoice_number(db)
    invoice = InvoiceDraft(
        project_id=project.id,
        inspection_report_id=inspection.id,
        invoice_number=invoice_number,
        claim_percentage=inspection.completion_pct,
        claim_amount_myr=claim_amount,
        status="draft",
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    log = ActivityLog(
        event_type="invoice_created",
        description=f"Invoice draft {invoice_number} created for {project.name}",
        entity_type="invoice_draft",
        entity_id=invoice.id,
    )
    db.add(log)
    session.state = "awaiting_invoice_confirm"
    session.context = {**(session.context or {}), "pending_invoice": {"invoice_id": invoice.id, "project_id": project.id}}
    await db.commit()
    await broadcast("invoice_created", log.description, "invoice_draft", invoice.id)

    pdf_bytes = generate_invoice_pdf(project, invoice)
    send_document(from_number, pdf_bytes, f"{invoice_number}.pdf", caption=f"Invoice {invoice_number}")
    send_message(
        from_number,
        f"Invoice {invoice_number} — RM {claim_amount:,.0f} ({float(inspection.completion_pct or 0):.0f}% claim).\n\n"
        "Approve to email this to the customer? Reply YES to confirm.",
    )


async def confirm_invoice(db: AsyncSession, session: ConversationSession, from_number: str) -> None:
    pending = (session.context or {}).get("pending_invoice")
    if not pending:
        send_message(from_number, "No pending invoice to confirm.")
        return

    invoice = await db.get(InvoiceDraft, pending["invoice_id"])
    project = await db.get(Project, pending["project_id"])
    if not invoice or not project:
        send_message(from_number, "Couldn't find that invoice anymore.")
        return

    invoice.status = "sent"
    session.state = "idle"
    session.context = {k: v for k, v in (session.context or {}).items() if k != "pending_invoice"}
    await db.commit()

    await broadcast("invoice_sent", f"Invoice {invoice.invoice_number} approved and sent", "invoice_draft", invoice.id)

    if settings.email_enabled and project.customer_email:
        pdf_bytes = generate_invoice_pdf(project, invoice)
        try:
            await send_email_with_attachment(
                project.customer_email,
                f"Progress Claim Invoice {invoice.invoice_number} — {project.name}",
                f"Please find attached progress claim invoice {invoice.invoice_number} "
                f"for {project.name} (RM {float(invoice.claim_amount_myr or 0):,.2f}).",
                pdf_bytes,
                f"{invoice.invoice_number}.pdf",
            )
            send_message(from_number, f"✅ Invoice {invoice.invoice_number} emailed to {project.customer_email}.")
        except Exception:  # noqa: BLE001
            logger.exception("invoice email failed for invoice=%s", invoice.id)
            send_message(from_number, f"✅ Invoice {invoice.invoice_number} approved, but the email send failed — check SMTP settings.")
    else:
        logger.info("[email:stub] invoice=%s would email customer=%s", invoice.invoice_number, project.customer_email)
        send_message(from_number, f"✅ Invoice {invoice.invoice_number} approved (email not configured — logged only).")


async def cancel_invoice(db: AsyncSession, session: ConversationSession, from_number: str) -> None:
    session.state = "idle"
    session.context = {k: v for k, v in (session.context or {}).items() if k != "pending_invoice"}
    await db.commit()
    send_message(from_number, "OK, invoice stays as a draft — not sent to the customer.")
