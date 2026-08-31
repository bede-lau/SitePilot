import asyncio
import csv
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.database import AsyncSessionLocal, Base, engine
from app.db_upgrade import run_upgrade
from app.models.models import (
    ActivityLog,
    Component,
    ConversationSession,
    InspectionReport,
    InvoiceDraft,
    Project,
    PurchaseOrder,
    Vendor,
)

logger = logging.getLogger("fieldbot.seed")

DATA_DIR = Path(__file__).parent / "data"

# Alias-matching CSV loader (ARD §9 / D4): Agent A's exact column headers for
# app/data/cec_modules.csv and cec_inverters.csv weren't finalized when this
# was written, so each Component field tries several plausible header
# spellings rather than assuming one. Missing columns just stay None.
_MODULE_FIELD_ALIASES = {
    "manufacturer": ["manufacturer", "brand", "mfr"],
    "model": ["model", "model_name", "part_number"],
    "tier": ["tier", "bnef_tier"],
    "rated_wp": ["rated_wp", "wp", "watts", "power_w", "pmax_w", "rated_power_w"],
    "vmp": ["vmp", "v_mp", "vmpp"],
    "voc": ["voc", "v_oc"],
    "imp": ["imp", "i_mp", "impp"],
    "isc": ["isc", "i_sc"],
    "temp_coeff_voc_pct_per_c": ["temp_coeff_voc_pct_per_c", "temp_coeff_voc", "beta_voc_pct_per_c", "voc_temp_coeff"],
    "efficiency_pct": ["efficiency_pct", "efficiency"],
    "cell_tech": ["cell_tech", "technology", "cell_technology"],
    "area_m2": ["area_m2", "area"],
    "datasheet_url": ["datasheet_url", "datasheet"],
}
_INVERTER_FIELD_ALIASES = {
    "manufacturer": ["manufacturer", "brand", "mfr"],
    "model": ["model", "model_name", "part_number"],
    "tier": ["tier", "bnef_tier"],
    "ac_rating_kw": ["ac_rating_kw", "ac_kw", "rated_ac_kw"],
    "max_dc_input_kw": ["max_dc_input_kw", "max_dc_kw", "dc_input_kw"],
    "mppt_min_v": ["mppt_min_v", "mppt_min"],
    "mppt_max_v": ["mppt_max_v", "mppt_max"],
    "max_dc_voltage_v": ["max_dc_voltage_v", "max_dc_v", "vmax_dc"],
    "max_input_current_per_mppt_a": ["max_input_current_per_mppt_a", "max_current_per_mppt", "imax_mppt"],
    "mppt_count": ["mppt_count", "num_mppt"],
    "phase": ["phase"],
    "euro_efficiency_pct": ["euro_efficiency_pct", "euro_efficiency"],
    "has_anti_islanding": ["has_anti_islanding", "anti_islanding"],
    "datasheet_url": ["datasheet_url", "datasheet"],
}
_NUMERIC_FIELDS = {
    "tier", "rated_wp", "vmp", "voc", "imp", "isc", "temp_coeff_voc_pct_per_c", "efficiency_pct", "area_m2",
    "ac_rating_kw", "max_dc_input_kw", "mppt_min_v", "mppt_max_v", "max_dc_voltage_v",
    "max_input_current_per_mppt_a", "mppt_count",
}
_BOOL_FIELDS = {"has_anti_islanding"}


def _extract(row: dict, aliases: dict[str, list[str]]) -> dict:
    row_lower = {k.strip().lower(): v for k, v in row.items() if k}
    out = {}
    for field, names in aliases.items():
        value = None
        for name in names:
            if name in row_lower and row_lower[name] not in (None, ""):
                value = row_lower[name]
                break
        if value is None:
            out[field] = None
            continue
        if field in _NUMERIC_FIELDS:
            try:
                out[field] = float(value)
                if field in ("tier", "mppt_count") and out[field] is not None:
                    out[field] = int(out[field])
            except (TypeError, ValueError):
                out[field] = None
        elif field in _BOOL_FIELDS:
            out[field] = str(value).strip().lower() in ("true", "1", "yes", "y")
        else:
            out[field] = str(value).strip()
    return out


def _load_components_from_csv(path: Path, kind: str, aliases: dict[str, list[str]]) -> list[Component]:
    if not path.exists():
        logger.warning("component CSV not found at %s — skipping %s catalog seed (Agent A hasn't landed it yet)", path, kind)
        return []
    components = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fields = _extract(row, aliases)
            if not fields.get("manufacturer") or not fields.get("model"):
                continue
            components.append(Component(kind=kind, source="CEC", **fields))
    return components


def days_ago(n: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


# Only the projects below get seeded history — fixed, deterministic demo data so
# their numbers never change between seed runs. Greenfield and KL Tech Park are
# the live demo projects driven through Telegram and start out with none.
STATIC_INSPECTIONS = {
    "Johor Bahru Rooftop Array": [
        {"age_days": 30, "panels_detected": 60, "panels_with_issues": 2,
         "issues": ["Loose mounting bracket", "Dust/debris accumulation reducing yield"], "completion_pct": 40.0},
        {"age_days": 10, "panels_detected": 105, "panels_with_issues": 1,
         "issues": ["Cracked panel glass"], "completion_pct": 70.0},
    ],
    "Sungai Petani Residential Cluster": [
        {"age_days": 85, "panels_detected": 15, "panels_with_issues": 0, "issues": [], "completion_pct": 25.0},
        {"age_days": 60, "panels_detected": 30, "panels_with_issues": 1,
         "issues": ["Shading from nearby vegetation"], "completion_pct": 50.0},
        {"age_days": 30, "panels_detected": 48, "panels_with_issues": 0, "issues": [], "completion_pct": 80.0},
        {"age_days": 5, "panels_detected": 60, "panels_with_issues": 1,
         "issues": ["Bird nesting under panel row"], "completion_pct": 100.0},
    ],
    "Kuching Eco Park Solar Farm": [
        {"age_days": 20, "panels_detected": 50, "panels_with_issues": 1,
         "issues": ["Junction box corrosion"], "completion_pct": 25.0},
        {"age_days": 5, "panels_detected": 110, "panels_with_issues": 0, "issues": [], "completion_pct": 55.0},
    ],
}

STATIC_INVOICE_STATUS = {
    "Johor Bahru Rooftop Array": ["sent", "draft"],
    "Sungai Petani Residential Cluster": ["approved", "approved", "approved", "approved"],
    "Kuching Eco Park Solar Farm": ["sent", "draft"],
}

STATIC_POS = {
    "Johor Bahru Rooftop Array": [
        {"vendor_name": "Apex Mounting Systems", "qty": 40, "status": "delivered", "age_days": 35},
        {"vendor_name": "Voltguard Electrical", "qty": 25, "status": "approved", "age_days": 15},
    ],
    "Sungai Petani Residential Cluster": [
        {"vendor_name": "YSP Solar Sdn Bhd", "qty": 60, "status": "delivered", "age_days": 90},
        {"vendor_name": "Green Energy Supply", "qty": 20, "status": "delivered", "age_days": 50},
    ],
    "Kuching Eco Park Solar Farm": [
        {"vendor_name": "Borneo PowerTech", "qty": 70, "status": "approved", "age_days": 18},
    ],
}


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await run_upgrade(conn)

    async with AsyncSessionLocal() as db:
        # --- ARD §9: existing 4 fixed-history projects + 2 live-demo projects keep
        # their exact name/email/contract_value/total_panels (source of truth).
        # New columns (state/system_type/monthly_consumption_kwh/tariff_category/
        # roof params/obstructions) are additive backfill only. Live-demo projects
        # (Greenfield, KL Tech Park) keep monthly_consumption_kwh=None per ARD §9.
        projects = [
            Project(
                name="Greenfield Industrial Solar Phase 1",
                client_name="Greenfield Manufacturing Sdn Bhd",
                site_location="Bayan Lepas, Penang",
                region="north",
                phase="Phase 1",
                total_panels=100,
                contract_value=150000.00,
                status="active",
                customer_email="orahome.mail+greenfield@gmail.com",
                created_at=days_ago(70),
                state="Penang",
                system_type="on_grid",
                tariff_category="commercial",
                obstructions=[],
            ),
            Project(
                name="KL Tech Park Phase 2",
                client_name="KLTP Holdings Berhad",
                site_location="Cyberjaya, Kuala Lumpur",
                region="central",
                phase="Phase 2",
                total_panels=80,
                contract_value=120000.00,
                status="active",
                customer_email="orahome.mail+kltp@gmail.com",
                created_at=days_ago(55),
                state="Selangor",
                system_type="on_grid",
                tariff_category="commercial",
                obstructions=[],
            ),
            Project(
                name="Johor Bahru Rooftop Array",
                client_name="JB Logistics Park Sdn Bhd",
                site_location="Tampoi, Johor Bahru",
                region="south",
                phase="Phase 1",
                total_panels=150,
                contract_value=210000.00,
                status="active",
                customer_email="orahome.mail+jblogistics@gmail.com",
                created_at=days_ago(40),
                state="Johor",
                system_type="on_grid",
                monthly_consumption_kwh=4800,
                tariff_category="commercial",
                roof_tilt_deg=10,
                roof_azimuth_deg=15,
                shading_factor=0.97,
                obstructions=[{"kind": "water_tank", "count": 1}],
            ),
            Project(
                name="Sungai Petani Residential Cluster",
                client_name="SP Township Developers",
                site_location="Sungai Petani, Kedah",
                region="north",
                phase="Phase 1",
                total_panels=60,
                contract_value=90000.00,
                status="completed",
                customer_email="orahome.mail+sptownship@gmail.com",
                created_at=days_ago(120),
                state="Kedah",
                system_type="hybrid",
                monthly_consumption_kwh=780,
                tariff_category="domestic",
                obstructions=[],
            ),
            Project(
                name="Kuching Eco Park Solar Farm",
                client_name="Sarawak Green Ventures",
                site_location="Kota Samarahan, Kuching",
                region="east",
                phase="Phase 1",
                total_panels=200,
                contract_value=280000.00,
                status="active",
                customer_email="orahome.mail+sarawakgreen@gmail.com",
                created_at=days_ago(25),
                state="Sarawak",
                system_type="on_grid",
                monthly_consumption_kwh=3100,
                tariff_category="commercial",
                roof_tilt_deg=12,
                roof_azimuth_deg=5,
                shading_factor=0.95,
                obstructions=[{"kind": "aircon_compressor", "count": 2}],
            ),
        ]
        db.add_all(projects)
        await db.flush()

        # contact_email uses +alias of the FieldBot mailbox (see backend/.env SMTP_USER) so
        # RFQs land in the same inbox you already control — no separate vendor accounts
        # needed. Replying to an RFQ from that same inbox simulates the vendor's response.
        # ARD §9: bnef_tier/brands_carried/quote_currency are additive backfill on
        # the existing 6 vendors — names/emails/rates/unit_price_myr unchanged.
        # Exactly one Tier-2 vendor (Green Energy Supply) and one USD vendor
        # (Borneo PowerTech, imported inverters) per the ARD spec.
        vendors = [
            Vendor(
                company_name="YSP Solar Sdn Bhd",
                region="north",
                contact_email="orahome.mail+ysp@gmail.com",
                on_time_rate=94.0,
                unit_price_myr=320.00,
                specialization="solar panels",
                bnef_tier=1,
                brands_carried=["Longi", "JA Solar"],
            ),
            Vendor(
                company_name="Green Energy Supply",
                region="north",
                contact_email="orahome.mail+greenenergy@gmail.com",
                on_time_rate=87.0,
                unit_price_myr=300.00,
                specialization="solar panels",
                bnef_tier=2,
                brands_carried=["SolarMax"],
            ),
            Vendor(
                company_name="SunTech Materials",
                region="central",
                contact_email="orahome.mail+suntech@gmail.com",
                on_time_rate=98.0,
                unit_price_myr=340.00,
                specialization="solar panels",
                bnef_tier=1,
                brands_carried=["Longi", "Trina Solar"],
            ),
            Vendor(
                company_name="Apex Mounting Systems",
                region="south",
                contact_email="orahome.mail+apex@gmail.com",
                on_time_rate=91.0,
                unit_price_myr=280.00,
                specialization="mounting structures",
                brands_carried=["Unirac", "IronRidge"],
            ),
            Vendor(
                company_name="Borneo PowerTech",
                region="east",
                contact_email="orahome.mail+borneo@gmail.com",
                on_time_rate=89.0,
                unit_price_myr=360.00,
                specialization="inverters & cabling",
                bnef_tier=1,
                brands_carried=["Huawei", "Sungrow"],
                quote_currency="USD",
            ),
            Vendor(
                company_name="Voltguard Electrical",
                region="central",
                contact_email="orahome.mail+voltguard@gmail.com",
                on_time_rate=96.0,
                unit_price_myr=250.00,
                specialization="electrical & balance-of-system",
                brands_carried=["Schneider Electric", "ABB"],
            ),
        ]
        db.add_all(vendors)
        await db.flush()

        activity_entries: list[ActivityLog] = []

        def log(event_type: str, description: str, entity_type: str, entity_id: int, when: datetime) -> None:
            activity_entries.append(
                ActivityLog(
                    event_type=event_type,
                    description=description,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    created_at=when,
                )
            )

        # --- Inspections: 2-4 per project, completion ramping up over time ---
        po_counter = 0
        for project in projects:
            if project.name in STATIC_INSPECTIONS:
                for i, spec in enumerate(STATIC_INSPECTIONS[project.name]):
                    when = days_ago(spec["age_days"])
                    insp = InspectionReport(
                        project_id=project.id,
                        submitted_by_phone=settings.demo_phone_number,
                        photo_urls=[],
                        panels_detected=spec["panels_detected"],
                        panels_with_issues=spec["panels_with_issues"],
                        issues=spec["issues"],
                        completion_pct=spec["completion_pct"],
                        ai_analysis_raw={"source": "seed_data"},
                        created_at=when,
                    )
                    db.add(insp)
                    await db.flush()
                    log(
                        "inspection_created",
                        f"AI inspection report created ({project.name}) — {spec['completion_pct']}% complete",
                        "inspection_report",
                        insp.id,
                        when,
                    )

                    claim_amount = round(float(project.contract_value) * spec["completion_pct"] / 100, 2)
                    invoice_when = when + timedelta(hours=6)
                    invoice = InvoiceDraft(
                        project_id=project.id,
                        inspection_report_id=insp.id,
                        invoice_number=f"INV-{project.id:02d}-{i + 1:02d}",
                        claim_percentage=spec["completion_pct"],
                        claim_amount_myr=claim_amount,
                        status=STATIC_INVOICE_STATUS[project.name][i],
                        created_at=invoice_when,
                    )
                    db.add(invoice)
                    await db.flush()
                    log(
                        "invoice_created",
                        f"Invoice draft {invoice.invoice_number} created ({spec['completion_pct']}% claim)",
                        "invoice_draft",
                        invoice.id,
                        invoice_when,
                    )

                for po_spec in STATIC_POS[project.name]:
                    vendor = next(v for v in vendors if v.company_name == po_spec["vendor_name"])
                    po_counter += 1
                    unit_price = float(vendor.unit_price_myr or 300)
                    total = round(po_spec["qty"] * unit_price, 2)
                    when = days_ago(po_spec["age_days"])
                    po = PurchaseOrder(
                        project_id=project.id,
                        vendor_id=vendor.id,
                        po_number=f"PO-{datetime.now(timezone.utc).year}-{po_counter:03d}",
                        item_description=f"{vendor.specialization or 'materials'} for {project.name}",
                        quantity=po_spec["qty"],
                        unit_price_myr=unit_price,
                        total_price_myr=total,
                        status=po_spec["status"],
                        created_at=when,
                    )
                    db.add(po)
                    if po_spec["status"] in ("approved", "delivered"):
                        project.budget_used_myr = float(project.budget_used_myr or 0) + total
                    await db.flush()
                    log(
                        "po_created",
                        f"{po.po_number} created for {vendor.company_name} (RM {total:,.0f})",
                        "purchase_order",
                        po.id,
                        when,
                    )
                continue

            # Greenfield and KL Tech Park are the live demo projects driven through
            # Telegram — they start as genuinely empty projects with zero history,
            # so every inspection/invoice/PO the bot creates is real, not seeded.

        db.add_all(activity_entries)

        session = ConversationSession(
            phone_number=settings.demo_phone_number,
            state="idle",
            context={"project_id": projects[0].id},
        )
        db.add(session)

        # --- ARD §9 / D4: components catalog from Agent A's vendored CEC CSVs. ---
        modules = _load_components_from_csv(DATA_DIR / "cec_modules.csv", "module", _MODULE_FIELD_ALIASES)
        inverters = _load_components_from_csv(DATA_DIR / "cec_inverters.csv", "inverter", _INVERTER_FIELD_ALIASES)
        db.add_all(modules)
        db.add_all(inverters)

        await db.commit()
        print(
            f"Seeded {len(projects)} projects, {len(vendors)} vendors, {len(activity_entries)} activity events, "
            f"{len(modules)} modules, {len(inverters)} inverters."
        )


if __name__ == "__main__":
    asyncio.run(seed())
