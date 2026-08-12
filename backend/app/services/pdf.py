"""PDF generation for documents shared with the manager/customer/vendor over
Telegram and email. Kept deliberately simple (reportlab platypus) — these are
internal ops documents, not branded customer collateral."""
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.models import InspectionReport, InvoiceDraft, Project

_styles = getSampleStyleSheet()


def _doc(buf: BytesIO) -> SimpleDocTemplate:
    return SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    table = Table(rows, colWidths=[55 * mm, 110 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.whitesmoke),
            ]
        )
    )
    return table


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def generate_inspection_pdf(project: Project, inspection: InspectionReport) -> bytes:
    buf = BytesIO()
    elements = [
        Paragraph("Site Inspection Report", _styles["Title"]),
        Paragraph(f"Generated {_now_str()}", _styles["Normal"]),
        Spacer(1, 10 * mm),
        _kv_table(
            [
                ("Project", project.name),
                ("Client", project.client_name),
                ("Site location", project.site_location),
                ("Panels detected", f"{inspection.panels_detected} of {project.total_panels}"),
                ("Panels with issues", str(inspection.panels_with_issues)),
                ("Completion", f"{float(inspection.completion_pct or 0):.0f}%"),
                ("Inspected", inspection.created_at.strftime("%Y-%m-%d %H:%M UTC") if inspection.created_at else "-"),
            ]
        ),
        Spacer(1, 8 * mm),
        Paragraph("Issues Flagged", _styles["Heading3"]),
    ]
    if inspection.issues:
        for issue in inspection.issues:
            elements.append(Paragraph(f"• {issue}", _styles["Normal"]))
    else:
        elements.append(Paragraph("No issues flagged.", _styles["Normal"]))

    _doc(buf).build(elements)
    return buf.getvalue()


def generate_invoice_pdf(project: Project, invoice: InvoiceDraft) -> bytes:
    buf = BytesIO()
    elements = [
        Paragraph(f"Progress Claim Invoice {invoice.invoice_number}", _styles["Title"]),
        Paragraph(f"Generated {_now_str()}", _styles["Normal"]),
        Spacer(1, 10 * mm),
        _kv_table(
            [
                ("Project", project.name),
                ("Client", project.client_name),
                ("Claim %", f"{float(invoice.claim_percentage or 0):.0f}%"),
                ("Contract value", f"RM {float(project.contract_value):,.2f}"),
                ("Claim amount", f"RM {float(invoice.claim_amount_myr or 0):,.2f}"),
                ("Status", invoice.status),
            ]
        ),
    ]
    _doc(buf).build(elements)
    return buf.getvalue()


def generate_po_pdf(project: Project | None, details: dict) -> bytes:
    """`details` matches the pending_po context shape used in agents/procurement.py
    (vendor_name, item_description, quantity, unit_price_myr, total_price_myr,
    delivery_days) — works for both the pre-approval draft and the final PO."""
    buf = BytesIO()
    rows = [
        ("Vendor", details.get("vendor_name", "-")),
        ("Item", details.get("item_description", "-")),
        ("Quantity", str(details.get("quantity", "-"))),
        ("Unit price", f"RM {float(details.get('unit_price_myr') or 0):,.2f}"),
        ("Total", f"RM {float(details.get('total_price_myr') or 0):,.2f}"),
        ("Delivery", f"{details.get('delivery_days', '-')} days"),
    ]
    if project:
        rows.insert(0, ("Project", project.name))
    elements = [
        Paragraph(f"Purchase Order — {details.get('po_number', 'Draft')}", _styles["Title"]),
        Paragraph(f"Generated {_now_str()}", _styles["Normal"]),
        Spacer(1, 10 * mm),
        _kv_table(rows),
    ]
    _doc(buf).build(elements)
    return buf.getvalue()
