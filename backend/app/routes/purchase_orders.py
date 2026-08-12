from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import ActivityLog, PurchaseOrder
from app.schemas import PurchaseOrderCreate
from app.services.events import broadcast

router = APIRouter()


@router.get("/purchase-orders")
async def list_purchase_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()))
    return result.scalars().all()


@router.post("/purchase-orders")
async def create_purchase_order(payload: PurchaseOrderCreate, db: AsyncSession = Depends(get_db)):
    po = PurchaseOrder(**payload.model_dump())
    db.add(po)
    await db.commit()
    await db.refresh(po)

    log = ActivityLog(
        event_type="po_created",
        description=f"{po.po_number} created",
        entity_type="purchase_order",
        entity_id=po.id,
    )
    db.add(log)
    await db.commit()

    await broadcast("po_created", log.description, "purchase_order", po.id)
    return po
