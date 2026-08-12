from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import InspectionReport, InvoiceDraft, Project, PurchaseOrder

router = APIRouter()


@router.get("/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project))
    return result.scalars().all()


@router.get("/projects/{project_id}")
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    inspections_count = len(
        (await db.execute(select(InspectionReport).where(InspectionReport.project_id == project_id))).scalars().all()
    )
    invoices_count = len(
        (await db.execute(select(InvoiceDraft).where(InvoiceDraft.project_id == project_id))).scalars().all()
    )
    pos_count = len(
        (await db.execute(select(PurchaseOrder).where(PurchaseOrder.project_id == project_id))).scalars().all()
    )

    return {
        "id": project.id,
        "name": project.name,
        "client_name": project.client_name,
        "site_location": project.site_location,
        "region": project.region,
        "phase": project.phase,
        "total_panels": project.total_panels,
        "contract_value": project.contract_value,
        "status": project.status,
        "created_at": project.created_at,
        "inspections_count": inspections_count,
        "invoices_count": invoices_count,
        "purchase_orders_count": pos_count,
    }
