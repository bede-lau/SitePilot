import asyncio
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import AsyncSessionLocal, Base, engine
from app.models.models import (
    ActivityLog,
    ConversationSession,
    InspectionReport,
    InvoiceDraft,
    Project,
    PurchaseOrder,
    Vendor,
)


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

    async with AsyncSessionLocal() as db:
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
            ),
        ]
        db.add_all(projects)
        await db.flush()

        # contact_email uses +alias of the FieldBot mailbox (see backend/.env SMTP_USER) so
        # RFQs land in the same inbox you already control — no separate vendor accounts
        # needed. Replying to an RFQ from that same inbox simulates the vendor's response.
        vendors = [
            Vendor(
                company_name="YSP Solar Sdn Bhd",
                region="north",
                contact_email="orahome.mail+ysp@gmail.com",
                on_time_rate=94.0,
                unit_price_myr=320.00,
                specialization="solar panels",
            ),
            Vendor(
                company_name="Green Energy Supply",
                region="north",
                contact_email="orahome.mail+greenenergy@gmail.com",
                on_time_rate=87.0,
                unit_price_myr=300.00,
                specialization="solar panels",
            ),
            Vendor(
                company_name="SunTech Materials",
                region="central",
                contact_email="orahome.mail+suntech@gmail.com",
                on_time_rate=98.0,
                unit_price_myr=340.00,
                specialization="solar panels",
            ),
            Vendor(
                company_name="Apex Mounting Systems",
                region="south",
                contact_email="orahome.mail+apex@gmail.com",
                on_time_rate=91.0,
                unit_price_myr=280.00,
                specialization="mounting structures",
            ),
            Vendor(
                company_name="Borneo PowerTech",
                region="east",
                contact_email="orahome.mail+borneo@gmail.com",
                on_time_rate=89.0,
                unit_price_myr=360.00,
                specialization="inverters & cabling",
            ),
            Vendor(
                company_name="Voltguard Electrical",
                region="central",
                contact_email="orahome.mail+voltguard@gmail.com",
                on_time_rate=96.0,
                unit_price_myr=250.00,
                specialization="electrical & balance-of-system",
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

        await db.commit()
        print(f"Seeded {len(projects)} projects, {len(vendors)} vendors, {len(activity_entries)} activity events.")


if __name__ == "__main__":
    asyncio.run(seed())
