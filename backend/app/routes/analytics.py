from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import InspectionReport, Project, PurchaseOrder, Vendor

router = APIRouter()


@router.get("/analytics/overview")
async def analytics_overview(db: AsyncSession = Depends(get_db)):
    projects = (await db.execute(select(Project))).scalars().all()
    vendors = (await db.execute(select(Vendor))).scalars().all()
    pos = (await db.execute(select(PurchaseOrder))).scalars().all()
    inspections = (await db.execute(select(InspectionReport))).scalars().all()

    spend_by_project: dict[int, float] = defaultdict(float)
    spend_by_vendor: dict[int, float] = defaultdict(float)
    orders_by_vendor: dict[int, int] = defaultdict(int)
    monthly_spend: dict[str, float] = defaultdict(float)

    for po in pos:
        total = float(po.total_price_myr or 0)
        spend_by_project[po.project_id] += total
        spend_by_vendor[po.vendor_id] += total
        orders_by_vendor[po.vendor_id] += 1
        month_key = po.created_at.strftime("%Y-%m")
        monthly_spend[month_key] += total

    project_budgets = []
    for p in projects:
        contract_value = float(p.contract_value)
        used = spend_by_project.get(p.id, 0.0)
        latest_completion = max(
            (i.completion_pct for i in inspections if i.project_id == p.id and i.completion_pct is not None),
            default=0.0,
        )
        project_budgets.append(
            {
                "project_id": p.id,
                "name": p.name,
                "region": p.region,
                "status": p.status,
                "contract_value": contract_value,
                "spend": round(used, 2),
                "budget_used_pct": round(min(used / contract_value * 100, 100), 1) if contract_value else 0,
                "completion_pct": round(float(latest_completion), 1),
            }
        )

    vendor_leaderboard = []
    for v in vendors:
        spend = spend_by_vendor.get(v.id, 0.0)
        orders = orders_by_vendor.get(v.id, 0)
        vendor_leaderboard.append(
            {
                "vendor_id": v.id,
                "company_name": v.company_name,
                "region": v.region,
                "specialization": v.specialization,
                "on_time_rate": float(v.on_time_rate or 0),
                "total_orders": orders,
                "total_spend": round(spend, 2),
            }
        )
    vendor_leaderboard.sort(key=lambda v: v["total_spend"], reverse=True)

    months_sorted = sorted(monthly_spend.keys())[-6:]
    spend_trend = [{"month": m, "amount": round(monthly_spend[m], 2)} for m in months_sorted]

    total_contract_value = sum(float(p.contract_value) for p in projects)
    total_spend = sum(spend_by_project.values())
    total_issues = sum(i.panels_with_issues for i in inspections)

    return {
        "total_contract_value": round(total_contract_value, 2),
        "total_spend": round(total_spend, 2),
        "active_projects": len([p for p in projects if p.status == "active"]),
        "completed_projects": len([p for p in projects if p.status == "completed"]),
        "total_panels_with_issues": total_issues,
        "project_budgets": project_budgets,
        "vendor_leaderboard": vendor_leaderboard,
        "spend_trend": spend_trend,
        "generated_at": datetime.now(timezone.utc),
    }
