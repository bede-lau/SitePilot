"""ARD §5.1 — feasibility endpoints. Thin HTTP layer over
app.services.feasibility_engine, shared with agents/tools.py's run_feasibility
tool."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import FeasibilityRun
from app.schemas import FeasibilityRequest
from app.services.feasibility_engine import FeasibilityError, run_feasibility_for_project

router = APIRouter(prefix="/api/feasibility", tags=["feasibility"])


@router.post("/run")
async def run_feasibility_endpoint(payload: FeasibilityRequest, db: AsyncSession = Depends(get_db)):
    try:
        run = await run_feasibility_for_project(
            db,
            project_id=payload.project_id,
            system_type=payload.system_type,
            panel_count=payload.panel_count,
            module=payload.module.model_dump(exclude_none=True) if payload.module else None,
            inverter=payload.inverter.model_dump(exclude_none=True) if payload.inverter else None,
            quote_id=payload.quote_id,
            monthly_consumption_kwh=payload.monthly_consumption_kwh,
            system_cost_myr=payload.system_cost_myr,
            budget_tier=payload.budget_tier,
            backup_hours=payload.backup_hours,
            critical_appliances=payload.critical_appliances,
        )
    except FeasibilityError as exc:
        status_code = 404 if "No project" in str(exc) else 503
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return run.results


@router.get("/{run_id}")
async def get_feasibility_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(FeasibilityRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Feasibility run not found")
    return run.results


@router.get("")
async def list_feasibility_runs(project_id: int, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(FeasibilityRun)
            .where(FeasibilityRun.project_id == project_id)
            .order_by(FeasibilityRun.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": r.id, "project_id": r.project_id, "system_type": r.system_type,
            "status": r.status, "confidence_score": r.confidence_score,
            "confidence_band": r.confidence_band, "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
