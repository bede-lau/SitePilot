from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Vendor

router = APIRouter()


@router.get("/vendors")
async def list_vendors(region: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Vendor).where(Vendor.is_active == True)  # noqa: E712
    if region:
        query = query.where(Vendor.region == region)
    result = await db.execute(query)
    return result.scalars().all()
