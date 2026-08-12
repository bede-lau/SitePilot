from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import ActivityLog, InvoiceDraft
from app.schemas import InvoiceCreate
from app.services.events import broadcast

router = APIRouter()


@router.get("/invoices")
async def list_invoices(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InvoiceDraft).order_by(InvoiceDraft.created_at.desc()))
    return result.scalars().all()


@router.post("/invoices")
async def create_invoice(payload: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    invoice = InvoiceDraft(**payload.model_dump())
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    log = ActivityLog(
        event_type="invoice_created",
        description=f"Invoice draft {invoice.invoice_number} created",
        entity_type="invoice_draft",
        entity_id=invoice.id,
    )
    db.add(log)
    await db.commit()

    await broadcast("invoice_created", log.description, "invoice_draft", invoice.id)
    return invoice
