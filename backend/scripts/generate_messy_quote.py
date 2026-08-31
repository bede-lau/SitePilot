"""Generates a deliberately messy supplier quotation PDF from REAL seeded DB rows —
the fixture that proves `agents/quote_parser.py` can actually read a document a
purchasing clerk would receive by email, not a clean synthetic table.

Every name and number on the page traces back to the database: the vendor's
company name, contact email, region and `unit_price_myr` come from the `vendors`
row; the module/inverter manufacturer, model and wattage come from the
`components` table (falling back to a small hardcoded list of the same real
models named in CLAUDE.md if that table doesn't exist yet). The only synthesised
figures are the secondary-line prices (inverter/BOS/freight) and the fake
registration/bank numbers in the letterhead — the `components` table (ARD §3.3)
carries no pricing, so those are derived from documented per-unit rates below,
not looked up.

Deliberate messiness, per ARD §7 (each comment below marks where):
  letterhead reg/SST numbers + bank block, inconsistent column alignment, a
  wrapped two-line row, a visually "merged" qty+unit cell, mixed units
  (pcs/nos/units/set/lot across fixtures), 1-2 USD line items with a footnote,
  wattage buried in description prose, warranty/lead-time only in a footnote,
  incoterms + validity clause, a rotated handwritten-style annotation, a page
  break mid-table with repeated headers, one typo, one inconsistent
  model-number format, a faint scan texture, and a rotated "RECEIVED" stamp.

CLI (run from `backend/`):
    python -m scripts.generate_messy_quote --vendor <id|name> --project <id|name> --out <path> --seed N
"""
import argparse
import asyncio
import io
import random
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.models import Project, Vendor

PAGE_W, PAGE_H = A4
MARGIN_L = 20 * mm
MARGIN_R = 20 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

INK = HexColor("#1a1a1a")
GREY = HexColor("#6b6b6b")
LIGHT_GREY = HexColor("#a8a8a8")
RULE = HexColor("#c9c9c9")
RED = HexColor("#a3231f")
BLUE_INK = HexColor("#1f3a93")

DEFAULT_FX_RATE = 4.72

# Fallback component specs — same real models cited in CLAUDE.md — used only if
# the `components` table (Agent A/C, ARD §3.3) doesn't exist yet at run time.
_FALLBACK_MODULES = [
    {"manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M", "rated_wp": 550},
    {"manufacturer": "Jinko", "model": "Tiger Neo JKM575N-72HL4-BDV", "rated_wp": 575},
    {"manufacturer": "Trina Solar", "model": "Vertex S+ TSM-DE09R.08", "rated_wp": 500},
]
_FALLBACK_INVERTERS = [
    {"manufacturer": "Huawei", "model": "SUN2000-10KTL-M1", "ac_rating_kw": 10},
    {"manufacturer": "Sungrow", "model": "SG5.0RS", "ac_rating_kw": 5},
]

MIXED_UNITS = ["nos", "pcs", "units"]


# --------------------------------------------------------------------------
# DB lookups — real rows only
# --------------------------------------------------------------------------

async def _find_vendor(db: AsyncSession, ident: str) -> Vendor:
    if ident.isdigit():
        vendor = await db.get(Vendor, int(ident))
        if vendor:
            return vendor
    result = await db.execute(select(Vendor).where(Vendor.company_name.ilike(f"%{ident}%")).limit(1))
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise SystemExit(f"No vendor matching '{ident}'")
    return vendor


async def _find_project(db: AsyncSession, ident: str) -> Project:
    if ident.isdigit():
        project = await db.get(Project, int(ident))
        if project:
            return project
    result = await db.execute(select(Project).where(Project.name.ilike(f"%{ident}%")).limit(1))
    project = result.scalar_one_or_none()
    if not project:
        raise SystemExit(f"No project matching '{ident}'")
    return project


async def _fetch_components(db: AsyncSession, kind: str) -> list[dict] | None:
    """Real rows from the `components` table (Agent A/C build this concurrently).
    Returns None if the table doesn't exist yet so the caller can fall back."""
    try:
        rows = (await db.execute(text("SELECT * FROM components WHERE kind = :kind"), {"kind": kind})).mappings().all()
    except Exception:
        return None
    return [dict(r) for r in rows] if rows else None


# --------------------------------------------------------------------------
# Deterministic content assembly
# --------------------------------------------------------------------------

def _fake_digits(rng: random.Random, n: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(n))


def _jitter_price(rng: random.Random, base: float, spread: float = 0.05) -> float:
    return round(base * (1 + rng.uniform(-spread, spread)), 2)


def build_line_items(vendor: Vendor, project: Project, module: dict, inverter: dict, rng: random.Random) -> dict:
    """Every figure here traces to `vendor`/`project`/`module`/`inverter` (DB rows)
    except the inverter/BOS/freight unit prices, which the `components` table
    (ARD §3.3) doesn't carry — those are synthesised from documented rates."""
    module_wp = module.get("rated_wp") or 550
    module_unit_price = _jitter_price(rng, float(vendor.unit_price_myr or 320.0))
    module_qty = project.total_panels if project.total_panels and project.total_panels <= 60 else rng.choice([15, 20, 24, 30])
    module_unit = rng.choice(MIXED_UNITS)  # ARD §7: mixed units across fixtures

    inverter_kw = inverter.get("ac_rating_kw") or 10
    inverter_cost_per_kw = 640.0  # documented assumption — components table has no price column
    inverter_price_myr = _jitter_price(rng, inverter_cost_per_kw * float(inverter_kw))
    use_usd = rng.random() < 0.5  # ARD §7: 1-2 line items in USD, exercises currency conversion
    inverter_currency = "USD" if use_usd else "MYR"
    inverter_price_display = round(inverter_price_myr / DEFAULT_FX_RATE, 2) if use_usd else inverter_price_myr

    bos_qty = max(1, -(-module_qty // 6))  # ceil(qty / 6) rail sets
    bos_price = _jitter_price(rng, 95.0)

    freight_price = _jitter_price(rng, 650.0 + 40.0 * (module_qty / 10))

    # ARD §7: wattage is buried in description prose, never its own column.
    # The manufacturer brand is stated (as any real quote would) so the parser has
    # something to split from the model string — it just isn't its own column.
    module_desc = (
        f"{module['manufacturer']} {module_wp}Wp N-type TOPCon monocrystalline solar module, black frame, "
        f"model {module['model']} — high efficiency dual-glass panel for tropical rooftop installation"
    )  # long on purpose: forces the wrapped two-line row

    # ARD §7: one inconsistent model-number format — dashes replaced with spaces
    # here, while the module's model string stays in its clean dashed form.
    inverter_model_printed = str(inverter["model"]).replace("-", " ")

    return {
        "rows": [
            {
                "description": module_desc, "manufacturer": module["manufacturer"], "model": module["model"],
                "qty": module_qty, "unit": module_unit, "unit_price": module_unit_price, "currency": "MYR",
                "wrap": True, "merge_qty_unit": False,
            },
            {
                "description": (
                    f"{inverter['manufacturer']} {inverter_kw}kW three-phase grid-tie string inverter, "
                    f"model {inverter_model_printed}"
                ),
                "manufacturer": inverter["manufacturer"], "model": inverter_model_printed,
                "qty": 1, "unit": "unit", "unit_price": inverter_price_display, "currency": inverter_currency,
                "wrap": False, "merge_qty_unit": False,
            },
            {
                "description": "Aluminium mounting rail set, 4.2m, incl. clamps & end caps",
                "manufacturer": "-", "model": "-",
                "qty": bos_qty, "unit": "set", "unit_price": bos_price, "currency": "MYR",
                "wrap": False, "merge_qty_unit": False,
            },
            {
                "description": f"Freight & delivery to site, {project.site_location}",
                "manufacturer": "-", "model": "-",
                "qty": 1, "unit": "lot", "unit_price": freight_price, "currency": "MYR",
                "wrap": False, "merge_qty_unit": True,  # ARD §7: visually "merged" qty+unit cell
            },
        ],
        "used_usd": use_usd,
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def _draw_scan_texture(c: canvas.Canvas, rng: random.Random) -> None:
    """Faint grey scan-like speckle across the page, drawn first so everything
    else layers on top of it. ARD §7."""
    c.saveState()
    c.setFillColor(Color(0, 0, 0, alpha=0.035))
    for _ in range(260):
        x = rng.uniform(0, PAGE_W)
        y = rng.uniform(0, PAGE_H)
        r = rng.uniform(0.2, 0.6)
        c.circle(x, y, r, stroke=0, fill=1)
    c.setStrokeColor(Color(0, 0, 0, alpha=0.02))
    c.setLineWidth(0.4)
    for _ in range(4):
        y = rng.uniform(0, PAGE_H)
        c.line(0, y, PAGE_W, y + rng.uniform(-6, 6))
    c.restoreState()


def _draw_received_stamp(c: canvas.Canvas, rng: random.Random, x: float, y: float) -> None:
    """Rotated, semi-transparent 'RECEIVED' stamp. ARD §7."""
    c.saveState()
    c.translate(x, y)
    c.rotate(-12)
    c.setStrokeColor(Color(*RED.rgb(), alpha=0.55))
    c.setFillColor(Color(*RED.rgb(), alpha=0.55))
    c.setLineWidth(1.4)
    c.roundRect(-2 * mm, -2 * mm, 44 * mm, 15 * mm, 2 * mm, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0, 5.5 * mm, "RECEIVED")
    c.setFont("Helvetica", 6.5)
    day = rng.randint(1, 28)
    c.drawString(0, 1.3 * mm, f"{day:02d} AUG 2026 — PROCUREMENT")
    c.restoreState()


def _draw_annotation(c: canvas.Canvas, x: float, y: float) -> None:
    """Rotated handwritten-style note. ARD §7."""
    c.saveState()
    c.translate(x, y)
    c.rotate(6)
    c.setFillColor(BLUE_INK)
    c.setFont("Helvetica-Oblique", 9.5)
    c.drawString(0, 0, "subject to stock — pls confirm by Fri")
    c.restoreState()


def _wrap_text(c: canvas.Canvas, text_: str, font: str, size: float, max_width: float) -> list[str]:
    words = text_.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if c.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


COLS = [
    ("No", 9 * mm),
    ("Description", 80 * mm),
    ("Qty", 16 * mm),
    ("Unit", 15 * mm),
    ("Unit Price", 25 * mm),
    ("Amount", 25 * mm),
]


def _col_x(index: int) -> float:
    x = MARGIN_L
    for i in range(index):
        x += COLS[i][1]
    return x


def _draw_table_header(c: canvas.Canvas, y: float) -> float:
    c.saveState()
    c.setFillColor(HexColor("#eeeeee"))
    c.rect(MARGIN_L, y - 6 * mm, CONTENT_W, 6 * mm, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.5)
    for i, (label, _) in enumerate(COLS):
        x = _col_x(i) + 1.5 * mm
        c.drawString(x, y - 4.3 * mm, label)
    c.restoreState()
    return y - 6 * mm


def _draw_row(c: canvas.Canvas, y_top: float, row: dict, line_no: int, rng: random.Random, fx_rate: float) -> float:
    """Draws one line item; returns the y coordinate below the row.
    ARD §7: per-row x jitter (misaligned columns), an optional two-line wrap,
    and an optional visually-merged qty+unit cell."""
    jitter = lambda: rng.uniform(-1.2, 1.6)  # noqa: E731 - tiny local helper, clearer inline
    font = "Helvetica"
    size = 8.3
    c.setFont(font, size)
    c.setFillColor(INK)

    desc_width = COLS[1][1] - 3 * mm
    desc_lines = _wrap_text(c, row["description"], font, size, desc_width) if row["wrap"] else [row["description"]]
    if not row["wrap"] and c.stringWidth(row["description"], font, size) > desc_width:
        desc_lines = _wrap_text(c, row["description"], font, size, desc_width)

    row_h = (5.0 * mm if len(desc_lines) <= 1 else 5.0 * mm + (len(desc_lines) - 1) * 4.0 * mm)
    baseline = y_top - 4.2 * mm

    c.drawString(_col_x(0) + 1.5 * mm + jitter(), baseline, str(line_no))
    for i, line in enumerate(desc_lines):
        c.drawString(_col_x(1) + 1.5 * mm, baseline - i * 4.0 * mm, line)

    unit_price_display = row["unit_price"]
    currency_prefix = "US$" if row["currency"] == "USD" else "RM"
    marker = "*" if row["currency"] == "USD" else ""

    if row["merge_qty_unit"]:
        c.drawString(_col_x(2) + 1.5 * mm + jitter(), baseline, f"{row['qty']} {row['unit']}")
    else:
        c.drawString(_col_x(2) + 1.5 * mm + jitter(), baseline, str(row["qty"]))
        c.drawString(_col_x(3) + 1.5 * mm + jitter(), baseline, row["unit"])

    c.drawString(_col_x(4) + 1.5 * mm, baseline, f"{currency_prefix} {unit_price_display:,.2f}{marker}")
    amount_myr = row["qty"] * (row["unit_price"] * fx_rate if row["currency"] == "USD" else row["unit_price"])
    c.drawString(_col_x(5) + 1.5 * mm, baseline, f"RM {amount_myr:,.2f}")

    bottom = y_top - row_h
    c.setStrokeColor(RULE)
    c.setLineWidth(0.4)
    c.line(MARGIN_L, bottom, MARGIN_L + CONTENT_W, bottom)
    return bottom


def render_quote_pdf(vendor: Vendor, project: Project, module: dict, inverter: dict, rng: random.Random, seed: int) -> bytes:
    """`rng` is one shared stream already advanced by the caller's module/inverter
    choice, so the whole document — component pick, pricing, and page messiness —
    is one deterministic draw sequence for a given `seed`. `seed` itself is only
    used for the human-readable quote number."""
    content = build_line_items(vendor, project, module, inverter, rng)
    rows = content["rows"]

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    now = datetime.now(timezone.utc)
    quote_no = f"QTN-{seed:04d}-{vendor.id:02d}"
    reg_no = f"{rng.randint(198000, 202699)}{_fake_digits(rng, 6)} ({_fake_digits(rng, 6)}-{rng.choice('ABCDEFHKMPTX')})"
    sst_no = f"W10-{_fake_digits(rng, 4)}-{_fake_digits(rng, 8)}"
    bank_acc = " ".join(_fake_digits(rng, 4) for _ in range(4))

    # --- Page 1: letterhead ---
    _draw_scan_texture(c, rng)
    y = PAGE_H - 22 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(MARGIN_L, y, vendor.company_name)
    y -= 5.2 * mm
    c.setFont("Helvetica", 8)
    c.setFillColor(GREY)
    c.drawString(MARGIN_L, y, f"Company Reg No (SSM): {reg_no}")
    y -= 3.6 * mm
    c.drawString(MARGIN_L, y, f"SST Reg No: {sst_no}    |    Region: {vendor.region.title()}, Malaysia")
    y -= 3.6 * mm
    c.drawString(MARGIN_L, y, f"Email: {vendor.contact_email}")

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(MARGIN_L + CONTENT_W, PAGE_H - 22 * mm, "QUOTATION")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(GREY)
    c.drawRightString(MARGIN_L + CONTENT_W, PAGE_H - 27.5 * mm, f"No: {quote_no}")
    c.drawRightString(MARGIN_L + CONTENT_W, PAGE_H - 32 * mm, f"Date: {now.strftime('%d %b %Y')}")

    y -= 8 * mm
    c.setStrokeColor(RULE)
    c.line(MARGIN_L, y, MARGIN_L + CONTENT_W, y)
    y -= 6 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN_L, y, "To:")
    c.setFont("Helvetica", 9)
    y -= 4.2 * mm
    c.drawString(MARGIN_L, y, project.client_name)
    y -= 4.2 * mm
    c.drawString(MARGIN_L, y, project.site_location)

    # Blank band between the "To:" block and the table — the annotation sits on
    # the left, the stamp on the right, far enough apart that neither the
    # letterhead text above nor each other's ink overlaps.
    y -= 6 * mm
    _draw_annotation(c, MARGIN_L, y)
    _draw_received_stamp(c, rng, MARGIN_L + CONTENT_W - 46 * mm, y - 2 * mm)

    y -= 14 * mm
    y = _draw_table_header(c, y)

    page = 1
    rows_first_page = 2  # ARD §7: force a page break mid-table
    for idx, row in enumerate(rows, start=1):
        if page == 1 and idx > rows_first_page:
            c.showPage()
            page = 2
            _draw_scan_texture(c, rng)
            y = PAGE_H - 22 * mm
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(MARGIN_L, y, f"Quotation {quote_no} (cont'd)")
            y -= 8 * mm
            y = _draw_table_header(c, y)  # repeated headers, per ARD §7
        y = _draw_row(c, y, row, idx, rng, DEFAULT_FX_RATE)

    y -= 8 * mm
    c.setFont("Helvetica", 7.5)
    c.setFillColor(GREY)
    if content["used_usd"]:
        c.drawString(MARGIN_L, y, f"* Price quoted in USD, converted to MYR @ {DEFAULT_FX_RATE} for reference only.")
        y -= 4 * mm

    # ARD §7: warranty/lead-time only in a free-text footnote, plus one deliberate typo ("Warrenty").
    c.drawString(
        MARGIN_L, y,
        "Warrenty: 25 years product/performance on modules, 10 years on inverter. "
        "Est. lead time: 21 days ARO, subject to stock.",
    )
    y -= 4 * mm
    c.drawString(
        MARGIN_L, y,
        "Incoterm: FOB Port Klang (modules), Ex-works Shah Alam (inverter/BOS). "
        "Prices valid 14 days from date of issue.",
    )
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(INK)
    c.drawString(MARGIN_L, y, "Payment details:")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(GREY)
    y -= 3.8 * mm
    c.drawString(MARGIN_L, y, f"{vendor.company_name} | Malayan Banking Berhad | Acc No: {bank_acc} | {vendor.region.title()} Branch")
    y -= 3.8 * mm
    c.drawString(MARGIN_L, y, "Terms: 30% deposit on PO, 70% before delivery.")

    c.showPage()
    c.save()
    return buf.getvalue()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

async def _build(vendor_ident: str, project_ident: str, seed: int) -> bytes:
    async with AsyncSessionLocal() as db:
        vendor = await _find_vendor(db, vendor_ident)
        project = await _find_project(db, project_ident)
        modules = await _fetch_components(db, "module") or _FALLBACK_MODULES
        inverters = await _fetch_components(db, "inverter") or _FALLBACK_INVERTERS

    rng = random.Random(seed)
    module = rng.choice(modules)
    inverter = rng.choice(inverters)
    return render_quote_pdf(vendor, project, module, inverter, rng, seed)


async def main_async(args: argparse.Namespace) -> None:
    pdf_bytes = await _build(args.vendor, args.project, args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(pdf_bytes)
    print(f"Wrote {out_path} ({len(pdf_bytes):,} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a deliberately messy supplier quote PDF from real seeded DB rows.")
    parser.add_argument("--vendor", required=True, help="Vendor id or a substring of its company name")
    parser.add_argument("--project", required=True, help="Project id or a substring of its name")
    parser.add_argument("--out", required=True, help="Output PDF path")
    parser.add_argument("--seed", type=int, default=1, help="Deterministic seed for content + messiness variation")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
