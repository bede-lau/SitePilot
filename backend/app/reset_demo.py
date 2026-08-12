"""Resets demo state between recording attempts.

Clears inspection_reports, invoice_drafts, purchase_orders, and activity_log.
Resets conversation_sessions to idle while keeping their project_id context
(so the demo phone stays pre-associated with project 1, per plan.txt Stage 6).
Projects and vendors are left untouched.

Run before each dry run / recording attempt:
    python -m app.reset_demo
"""
import asyncio

from sqlalchemy import delete, select, update

from app.database import AsyncSessionLocal
from app.models.models import (
    ActivityLog,
    ConversationSession,
    InspectionReport,
    InvoiceDraft,
    Project,
    PurchaseOrder,
    RFQ,
)


async def reset_demo():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(PurchaseOrder))
        await db.execute(delete(RFQ))
        await db.execute(delete(InvoiceDraft))
        await db.execute(delete(InspectionReport))
        await db.execute(delete(ActivityLog))
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
        print("Demo reset: inspections, invoices, POs, RFQs, activity log cleared; budget_used reset; sessions set to idle; chat history cleared.")


if __name__ == "__main__":
    asyncio.run(reset_demo())
