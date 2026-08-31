"""ARD §5.1 — GET /api/overview: fleet KPIs for the Command Center dashboard.

Real DB rows only — no fabricated numbers. Design-derived metrics (capacity,
confidence, generation) come from each project's *latest* `feasibility_runs`
row; a project with no feasibility run yet simply contributes 0, it is not
estimated. co2_avoided_tonnes uses the Malaysia grid emission factor
0.585 tCO2/MWh (documented in the response as an assumption, per ARD)."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import FeasibilityRun, InspectionReport, Project, PurchaseOrder, RFQ

router = APIRouter(prefix="/api", tags=["overview"])

CO2_FACTOR_TONNES_PER_MWH = 0.585  # Malaysia grid emission factor (ARD §5.1)


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _last_12_months(now: datetime) -> list[str]:
    months = []
    cursor = now.replace(day=1)
    for _ in range(12):
        months.append(_month_key(cursor))
        # step back one month
        prev_end = cursor - timedelta(days=1)
        cursor = prev_end.replace(day=1)
    return list(reversed(months))


@router.get("/overview")
async def get_overview(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)

    projects = (await db.execute(select(Project))).scalars().all()
    all_runs = (
        await db.execute(select(FeasibilityRun).order_by(FeasibilityRun.created_at.asc()))
    ).scalars().all()

    # latest run per project
    latest_run_by_project: dict[int, FeasibilityRun] = {}
    for run in all_runs:
        latest_run_by_project[run.project_id] = run  # runs are ordered asc, so last write wins

    total_capacity_kwp = 0.0
    confidence_scores: list[int] = []
    monthly_generation_by_project: dict[int, float] = {}
    for project in projects:
        run = latest_run_by_project.get(project.id)
        if not run or not run.results:
            continue
        array = run.results.get("array") or {}
        financial = run.results.get("financial") or {}
        confidence = run.results.get("confidence") or {}
        actual_kwp = array.get("actual_kwp")
        if actual_kwp is not None:
            total_capacity_kwp += float(actual_kwp)
        if confidence.get("score") is not None:
            confidence_scores.append(int(confidence["score"]))
        gen = financial.get("monthly_generation_kwh")
        if gen is not None:
            monthly_generation_by_project[project.id] = float(gen)

    active_projects = len([p for p in projects if p.status == "active"])

    open_rfqs = (
        await db.execute(select(func.count()).select_from(RFQ).where(RFQ.status == "sent"))
    ).scalar_one()

    po_value_myr = (
        await db.execute(select(func.coalesce(func.sum(PurchaseOrder.total_price_myr), 0)))
    ).scalar_one()

    avg_confidence = round(sum(confidence_scores) / len(confidence_scores), 1) if confidence_scores else None

    # panels_installed: latest inspection's panels_detected per project (real field data,
    # not the project's target total_panels).
    inspections = (
        await db.execute(select(InspectionReport).order_by(InspectionReport.created_at.asc()))
    ).scalars().all()
    latest_panels_by_project: dict[int, int] = {}
    for insp in inspections:
        if insp.panels_detected is not None:
            latest_panels_by_project[insp.project_id] = insp.panels_detected
    panels_installed = sum(latest_panels_by_project.values())

    annual_generation_kwh = sum(monthly_generation_by_project.values()) * 12
    co2_avoided_tonnes = round(annual_generation_kwh / 1000 * CO2_FACTOR_TONNES_PER_MWH, 2)

    # --- 12-month generation_trend: cumulative ramp as each project's latest
    # feasibility-run generation estimate "comes online" from its created_at month.
    # Projects without a feasibility run contribute 0 (not estimated).
    months = _last_12_months(now)
    generation_trend = []
    for month in months:
        month_dt = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
        total = 0.0
        for project in projects:
            if project.created_at and _month_key(project.created_at.replace(tzinfo=timezone.utc)) <= month:
                total += monthly_generation_by_project.get(project.id, 0.0)
        generation_trend.append({"month": month, "value": round(total, 1)})

    # --- 12-month spend_trend from real PurchaseOrder rows ---
    pos = (await db.execute(select(PurchaseOrder))).scalars().all()
    spend_by_month: dict[str, float] = defaultdict(float)
    for po in pos:
        if po.created_at:
            spend_by_month[_month_key(po.created_at.replace(tzinfo=timezone.utc))] += float(po.total_price_myr or 0)
    spend_trend = [{"month": m, "value": round(spend_by_month.get(m, 0.0), 2)} for m in months]

    return {
        "total_capacity_kwp": round(total_capacity_kwp, 2),
        "active_projects": active_projects,
        "open_rfqs": open_rfqs,
        "po_value_myr": round(float(po_value_myr or 0), 2),
        "avg_confidence": avg_confidence,
        "panels_installed": panels_installed,
        "co2_avoided_tonnes": co2_avoided_tonnes,
        "co2_factor_assumption": f"{CO2_FACTOR_TONNES_PER_MWH} tCO2/MWh (Malaysia grid emission factor)",
        "generation_trend": generation_trend,
        "spend_trend": spend_trend,
        "generated_at": now.isoformat(),
    }
