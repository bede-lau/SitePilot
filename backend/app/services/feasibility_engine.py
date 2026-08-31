"""Shared feasibility-run logic used by routes/feasibility.py (dashboard) and
agents/tools.py's run_feasibility tool (chat), so both entry points build the
same DesignInputs and persist the same way.

Delegates all arithmetic to Agent A's app.engine.report.run_design — imported
lazily so this module still loads before engine/report.py (and its
dependents: inverter.py, battery.py, bos.py, financial.py, confidence.py) land
(ARD §1 "the LLM never does arithmetic" rule: this module does no math either,
it only assembles inputs and persists the engine's output verbatim).

engine.types.DesignInputs/ModuleSpec/InverterSpec/Obstruction are confirmed
(app/engine/types.py landed) — `_build_inputs` below constructs them exactly
per that contract."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Component, FeasibilityRun, InspectionReport, Project, SupplierQuote

logger = logging.getLogger("fieldbot.feasibility")

# Fallback module spec (spec §12.5) used only if app.engine.constants isn't
# importable yet AND the caller supplied no module — mirrors
# engine.constants.DEFAULT_MODULE_550W so behaviour matches once it lands.
_FALLBACK_MODULE_550W = {
    "manufacturer": "Generic", "model": "Standard 550W Reference Module", "rated_wp": 550.0,
    "vmp": 41.5, "voc": 49.6, "imp": 13.2, "isc": 14.0, "temp_coeff_voc_pct_per_c": None,
}


class FeasibilityError(Exception):
    """Caller-facing failure (missing project, engine not landed, etc.)."""


def _default_module_dict() -> dict:
    try:
        from app.engine.constants import DEFAULT_MODULE_550W  # Agent A — lazy import

        return dict(DEFAULT_MODULE_550W)
    except ImportError:
        return dict(_FALLBACK_MODULE_550W)


def _module_spec_from_dict(d: dict):
    from app.engine.types import ModuleSpec

    fallback = _default_module_dict()
    return ModuleSpec(
        manufacturer=d.get("manufacturer") or fallback["manufacturer"],
        model=d.get("model") or fallback["model"],
        rated_wp=float(d.get("rated_wp") or fallback["rated_wp"]),
        vmp=float(d.get("vmp") or fallback["vmp"]),
        voc=float(d.get("voc") or fallback["voc"]),
        imp=float(d.get("imp") or fallback["imp"]),
        isc=float(d.get("isc") or fallback["isc"]),
        temp_coeff_voc_pct_per_c=d.get("temp_coeff_voc_pct_per_c"),
    )


def _component_to_module_spec(c: Component):
    from app.engine.types import ModuleSpec

    fallback = _default_module_dict()
    return ModuleSpec(
        manufacturer=c.manufacturer,
        model=c.model,
        rated_wp=float(c.rated_wp) if c.rated_wp is not None else fallback["rated_wp"],
        vmp=float(c.vmp) if c.vmp is not None else fallback["vmp"],
        voc=float(c.voc) if c.voc is not None else fallback["voc"],
        imp=float(c.imp) if c.imp is not None else fallback["imp"],
        isc=float(c.isc) if c.isc is not None else fallback["isc"],
        temp_coeff_voc_pct_per_c=float(c.temp_coeff_voc_pct_per_c) if c.temp_coeff_voc_pct_per_c is not None else None,
        bnef_tier1=(c.tier == 1) if c.tier is not None else None,
    )


def _component_to_inverter_spec(c: Component):
    from app.engine.types import InverterSpec

    return InverterSpec(
        manufacturer=c.manufacturer,
        model=c.model,
        ac_rating_kw=float(c.ac_rating_kw or 0),
        max_dc_input_kw=float(c.max_dc_input_kw or 0),
        mppt_min_v=float(c.mppt_min_v or 0),
        mppt_max_v=float(c.mppt_max_v or 0),
        max_dc_voltage_v=float(c.max_dc_voltage_v or 0),
        max_input_current_per_mppt_a=float(c.max_input_current_per_mppt_a or 0),
        mppt_count=int(c.mppt_count or 1),
        phase=c.phase if c.phase in ("single", "three") else "single",
        has_anti_islanding=bool(c.has_anti_islanding) if c.has_anti_islanding is not None else True,
    )


def _inverter_spec_from_dict(d: dict):
    from app.engine.types import InverterSpec

    ac_kw = float(d.get("ac_rating_kw") or 0)
    return InverterSpec(
        manufacturer=d.get("manufacturer") or "Custom",
        model=d.get("model") or "Custom",
        ac_rating_kw=ac_kw,
        max_dc_input_kw=float(d.get("max_dc_input_kw") or ac_kw * 1.5),
        mppt_min_v=float(d.get("mppt_min_v") or 120),
        mppt_max_v=float(d.get("mppt_max_v") or 500),
        max_dc_voltage_v=float(d.get("max_dc_voltage_v") or 1000),
        max_input_current_per_mppt_a=float(d.get("max_input_current_per_mppt_a") or 15),
        mppt_count=int(d.get("mppt_count") or 2),
        phase=d.get("phase") if d.get("phase") in ("single", "three") else "single",
        has_anti_islanding=True,
    )


async def _resolve_panel_count(db: AsyncSession, project: Project, requested: int | None) -> tuple[int | None, bool]:
    """Returns (panel_count, from_field_photo)."""
    if requested is not None:
        return requested, False
    latest = (
        await db.execute(
            select(InspectionReport)
            .where(InspectionReport.project_id == project.id)
            .order_by(InspectionReport.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest and latest.panels_detected:
        return latest.panels_detected, True
    return None, False


async def _resolve_module(db: AsyncSession, module_ref: dict | None, quote: SupplierQuote | None):
    """Returns (ModuleSpec, component_id_or_None)."""
    if module_ref and module_ref.get("component_id"):
        c = await db.get(Component, module_ref["component_id"])
        if c:
            return _component_to_module_spec(c), c.id
    if module_ref and module_ref.get("rated_wp"):
        return _module_spec_from_dict(module_ref), None
    if quote:
        for li in quote.line_items:
            if li.category == "module" and li.rated_wp:
                return (
                    _module_spec_from_dict(
                        {"manufacturer": li.manufacturer, "model": li.model, "rated_wp": float(li.rated_wp)}
                    ),
                    None,
                )
    return _module_spec_from_dict({}), None


async def _resolve_inverter(db: AsyncSession, inverter_ref: dict | None):
    """Returns (InverterSpec_or_None, component_id_or_None, catalog_tuple_for_autoselect)."""
    if inverter_ref and inverter_ref.get("component_id"):
        c = await db.get(Component, inverter_ref["component_id"])
        if c:
            return _component_to_inverter_spec(c), c.id, ()
    if inverter_ref and inverter_ref.get("ac_rating_kw"):
        return _inverter_spec_from_dict(inverter_ref), None, ()
    # No explicit inverter -> auto-select. Engine does no DB I/O (ARD §1), so we
    # supply the candidate catalog from our own `components` table.
    rows = (await db.execute(select(Component).where(Component.kind == "inverter"))).scalars().all()
    catalog = tuple(_component_to_inverter_spec(c) for c in rows)
    return None, None, catalog


def _to_dict(report) -> dict:
    if hasattr(report, "as_dict"):
        return report.as_dict()
    if isinstance(report, dict):
        return report
    import dataclasses

    if dataclasses.is_dataclass(report):
        return dataclasses.asdict(report)
    if hasattr(report, "model_dump"):
        return report.model_dump()
    return dict(vars(report))


async def run_feasibility_for_project(
    db: AsyncSession,
    *,
    project_id: int,
    system_type: str | None = None,
    panel_count: int | None = None,
    module: dict | None = None,
    inverter: dict | None = None,
    quote_id: int | None = None,
    monthly_consumption_kwh: float | None = None,
    system_cost_myr: float | None = None,
    budget_tier: str = "mid",
    backup_hours: float | None = None,
    critical_appliances: list[str] | None = None,
) -> FeasibilityRun:
    project = await db.get(Project, project_id)
    if not project:
        raise FeasibilityError(f"No project with id {project_id}")

    try:
        from app.engine.report import run_design  # Agent A — lazy import
        from app.engine.types import DesignInputs, Obstruction
    except ImportError as exc:
        raise FeasibilityError("Feasibility engine not available yet (app.engine.report not landed)") from exc

    quote = await db.get(SupplierQuote, quote_id) if quote_id else None
    if quote:
        await db.refresh(quote, attribute_names=["line_items"])

    resolved_system_type = system_type or project.system_type or "on_grid"
    resolved_panel_count, from_photo = await _resolve_panel_count(db, project, panel_count)
    module_spec, module_component_id = await _resolve_module(db, module, quote)
    inverter_spec, inverter_component_id, inverter_catalog = await _resolve_inverter(db, inverter)
    resolved_monthly_kwh = monthly_consumption_kwh if monthly_consumption_kwh is not None else (
        float(project.monthly_consumption_kwh) if project.monthly_consumption_kwh is not None else None
    )
    resolved_cost = system_cost_myr
    if resolved_cost is None and quote and quote.subtotal_myr is not None:
        resolved_cost = float(quote.subtotal_myr)

    obstructions = tuple(
        Obstruction(kind=o.get("kind", "unknown"), count=int(o.get("count", 1)))
        for o in (project.obstructions or [])
        if isinstance(o, dict) and o.get("kind")
    )

    inputs = DesignInputs(
        generated_at=datetime.now(timezone.utc).isoformat(),
        module=module_spec,
        system_type=resolved_system_type,
        project_id=project_id,
        panel_count=resolved_panel_count,
        panel_count_source="photo" if from_photo else "manual",
        inverter=inverter_spec,
        inverter_catalog=inverter_catalog,
        monthly_consumption_kwh=resolved_monthly_kwh,
        state=project.state,
        roof_area_m2=float(project.roof_area_m2) if project.roof_area_m2 is not None else None,
        roof_tilt_deg=float(project.roof_tilt_deg) if project.roof_tilt_deg is not None else None,
        roof_azimuth_deg=float(project.roof_azimuth_deg) if project.roof_azimuth_deg is not None else None,
        shading_factor=float(project.shading_factor) if project.shading_factor is not None else None,
        obstructions=obstructions,
        system_cost_myr=resolved_cost,
        budget_tier=budget_tier,
        tariff_category=project.tariff_category or "domestic",
        backup_hours=backup_hours,
        critical_appliances=tuple(critical_appliances or []),
        has_supplier_quote=quote is not None,
    )

    report = run_design(inputs)
    results = _to_dict(report)

    run = FeasibilityRun(
        project_id=project_id,
        quote_id=quote_id,
        module_component_id=module_component_id,
        inverter_component_id=inverter_component_id,
        system_type=resolved_system_type,
        inputs={
            "system_type": resolved_system_type, "panel_count": resolved_panel_count,
            "quote_id": quote_id, "monthly_consumption_kwh": resolved_monthly_kwh,
            "system_cost_myr": resolved_cost, "budget_tier": budget_tier,
            "backup_hours": backup_hours, "critical_appliances": list(critical_appliances or []),
        },
        results={},
        status=results.get("status", "pass"),
        confidence_score=(results.get("confidence") or {}).get("score"),
        confidence_band=(results.get("confidence") or {}).get("band"),
    )
    db.add(run)
    await db.flush()

    results["id"] = run.id
    results["project_id"] = project_id
    run.results = results

    await db.commit()
    await db.refresh(run)
    return run
