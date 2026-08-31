"""ARD §5.1 — GET /api/components, GET /api/bnef/check.

Catalog browser over the `components` table (seeded from the CEC CSVs by
Agent A's app/data/*.csv, loaded in seed.py) and a thin wrapper over Agent A's
BNEF tier registry (app/data/bnef.py — imported lazily so this router, and the
rest of the app, still boots before that module lands)."""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Component

logger = logging.getLogger("fieldbot.components")

router = APIRouter(prefix="/api", tags=["components"])


def _serialize(c: Component) -> dict:
    return {
        "id": c.id,
        "kind": c.kind,
        "manufacturer": c.manufacturer,
        "model": c.model,
        "tier": c.tier,
        "rated_wp": float(c.rated_wp) if c.rated_wp is not None else None,
        "vmp": float(c.vmp) if c.vmp is not None else None,
        "voc": float(c.voc) if c.voc is not None else None,
        "imp": float(c.imp) if c.imp is not None else None,
        "isc": float(c.isc) if c.isc is not None else None,
        "temp_coeff_voc_pct_per_c": float(c.temp_coeff_voc_pct_per_c) if c.temp_coeff_voc_pct_per_c is not None else None,
        "efficiency_pct": float(c.efficiency_pct) if c.efficiency_pct is not None else None,
        "cell_tech": c.cell_tech,
        "area_m2": float(c.area_m2) if c.area_m2 is not None else None,
        "ac_rating_kw": float(c.ac_rating_kw) if c.ac_rating_kw is not None else None,
        "max_dc_input_kw": float(c.max_dc_input_kw) if c.max_dc_input_kw is not None else None,
        "mppt_min_v": float(c.mppt_min_v) if c.mppt_min_v is not None else None,
        "mppt_max_v": float(c.mppt_max_v) if c.mppt_max_v is not None else None,
        "max_dc_voltage_v": float(c.max_dc_voltage_v) if c.max_dc_voltage_v is not None else None,
        "max_input_current_per_mppt_a": float(c.max_input_current_per_mppt_a) if c.max_input_current_per_mppt_a is not None else None,
        "mppt_count": c.mppt_count,
        "phase": c.phase,
        "euro_efficiency_pct": float(c.euro_efficiency_pct) if c.euro_efficiency_pct is not None else None,
        "has_anti_islanding": c.has_anti_islanding,
        "datasheet_url": c.datasheet_url,
        "source": c.source,
    }


@router.get("/components")
async def list_components(
    kind: str | None = Query(default=None, description="module | inverter"),
    q: str | None = Query(default=None, description="Search manufacturer/model"),
    limit: int = Query(default=50, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(Component)
    if kind:
        query = query.where(Component.kind == kind)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Component.manufacturer.ilike(like), Component.model.ilike(like)))
    query = query.order_by(Component.manufacturer, Component.model).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return [_serialize(c) for c in rows]


@router.get("/components/{component_id}")
async def get_component(component_id: int, db: AsyncSession = Depends(get_db)):
    c = await db.get(Component, component_id)
    if not c:
        return {"error": f"No component with id {component_id}"}
    return _serialize(c)


@router.get("/bnef/check")
async def check_bnef(manufacturer: str = Query(...)):
    """{manufacturer, tier1, matched_name, source} — ARD §5.1."""
    try:
        from app.data.bnef import match_manufacturer  # Agent A — lazy import
    except ImportError:
        logger.warning("app.data.bnef not available yet — BNEF check stubbed")
        return {"manufacturer": manufacturer, "tier1": False, "matched_name": None, "source": "unavailable"}

    is_tier1, matched_name = match_manufacturer(manufacturer)
    return {
        "manufacturer": manufacturer,
        "tier1": bool(is_tier1),
        "matched_name": matched_name,
        "source": "bnef_registry",
    }
