from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import ActivityLog, InspectionReport
from app.schemas import InspectionCreate
from app.services.events import broadcast

router = APIRouter()


@router.get("/inspections")
async def list_inspections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InspectionReport).order_by(InspectionReport.created_at.desc()))
    return result.scalars().all()


@router.get("/inspections/{inspection_id}")
async def get_inspection(inspection_id: int, db: AsyncSession = Depends(get_db)):
    inspection = await db.get(InspectionReport, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection


@router.post("/inspections")
async def create_inspection(payload: InspectionCreate, db: AsyncSession = Depends(get_db)):
    inspection = InspectionReport(**payload.model_dump())
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)

    log = ActivityLog(
        event_type="inspection_created",
        description=f"AI inspection report created (project {inspection.project_id})",
        entity_type="inspection_report",
        entity_id=inspection.id,
    )
    db.add(log)
    await db.commit()

    await broadcast("inspection_created", log.description, "inspection_report", inspection.id)
    return inspection
