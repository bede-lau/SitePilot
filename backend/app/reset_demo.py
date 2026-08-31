"""Resets demo state between recording attempts.

Clears inspection_reports, invoice_drafts, purchase_orders, activity_log, and
(ARD §9) the new transactional tables — supplier_quotes, quote_line_items,
feasibility_runs, chat_messages. Resets conversation_sessions to idle while
keeping their project_id context (so the demo phone stays pre-associated with
project 1, per plan.txt Stage 6). Projects, vendors, and the `components`
catalog are left untouched (components is reference data, not demo state).

Run before each dry run / recording attempt:
    python -m app.reset_demo
"""
import asyncio

from sqlalchemy import delete, select, update

from app.database import AsyncSessionLocal
from app.models.models import (
    ActivityLog,
    ChatMessage,
    ConversationSession,
    FeasibilityRun,
    InspectionReport,
    InvoiceDraft,
    Project,
    PurchaseOrder,
    QuoteLineItem,
    RFQ,
    SupplierQuote,
)


async def reset_demo():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(PurchaseOrder))
        await db.execute(delete(RFQ))
        await db.execute(delete(InvoiceDraft))
        await db.execute(delete(InspectionReport))
        await db.execute(delete(ActivityLog))
        # children before parents (no FK cascade configured)
        await db.execute(delete(QuoteLineItem))
        await db.execute(delete(FeasibilityRun))
        await db.execute(delete(SupplierQuote))
        await db.execute(delete(ChatMessage))
        await db.execute(update(ConversationSession).values(state="idle"))
        await db.execute(update(Project).values(budget_used_myr=0))

        # Strip transient conversation context (chat history, pending PO/invoice,
        # last inspection) but keep each session's project_id binding. Stale chat
        # history can otherwise poison the orchestrator into repeating an old reply
        # instead of acting on a fresh request.
        sessions = (await db.execute(select(ConversationSession))).scalars().all()
        for s in sessions:
            project_id = (s.context or {}).get("project_id")
            s.context = {"project_id": project_id} if project_id is not None else {}
        await db.commit()
        print(
            "Demo reset: inspections, invoices, POs, RFQs, activity log, supplier quotes, "
            "feasibility runs, chat messages cleared; budget_used reset; sessions set to idle "
            "(components catalog untouched)."
        )


if __name__ == "__main__":
    asyncio.run(reset_demo())
