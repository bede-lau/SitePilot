from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    client_name: Mapped[str] = mapped_column(String, nullable=False)
    site_location: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False)
    phase: Mapped[str | None] = mapped_column(String, nullable=True)
    total_panels: Mapped[int] = mapped_column(nullable=False)
    contract_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")
    customer_email: Mapped[str | None] = mapped_column(String, nullable=True)
    budget_used_myr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    # --- ARD §3.1: feasibility/engineering inputs (additive, all nullable/defaulted) ---
    state: Mapped[str] = mapped_column(String, default="Selangor")
    system_type: Mapped[str] = mapped_column(String, default="on_grid")  # on_grid | hybrid
    monthly_consumption_kwh: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    tariff_category: Mapped[str] = mapped_column(String, default="domestic")  # domestic | commercial
    roof_area_m2: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    roof_tilt_deg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    roof_azimuth_deg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    shading_factor: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    obstructions: Mapped[list] = mapped_column(JSON, default=list)

    inspection_reports: Mapped[list["InspectionReport"]] = relationship(back_populates="project")
    invoice_drafts: Mapped[list["InvoiceDraft"]] = relationship(back_populates="project")
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="project")


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str] = mapped_column(String, nullable=False)
    contact_email: Mapped[str] = mapped_column(String, nullable=False)
    on_time_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    unit_price_myr: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    # --- ARD §3.2 ---
    bnef_tier: Mapped[int | None] = mapped_column(nullable=True)  # 1 | 2
    brands_carried: Mapped[list] = mapped_column(JSON, default=list)
    country: Mapped[str] = mapped_column(String, default="Malaysia")
    quote_currency: Mapped[str] = mapped_column(String, default="MYR")


class InspectionReport(Base):
    __tablename__ = "inspection_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    submitted_by_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_urls: Mapped[list] = mapped_column(JSON, default=list)
    panels_detected: Mapped[int | None] = mapped_column(nullable=True)
    panels_with_issues: Mapped[int] = mapped_column(default=0)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    completion_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ai_analysis_raw: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    project: Mapped["Project"] = relationship(back_populates="inspection_reports")


class InvoiceDraft(Base):
    __tablename__ = "invoice_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    inspection_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspection_reports.id"), nullable=True
    )
    invoice_number: Mapped[str] = mapped_column(String, nullable=False)
    claim_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    claim_amount_myr: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    project: Mapped["Project"] = relationship(back_populates="invoice_drafts")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    # Nullable: services/po_engine.py's generate_po() intentionally creates a status="draft" PO
    # with vendor_id=None when a feasibility run's quote didn't resolve to a matched vendor (ARD
    # §5.1 also documents PoGenerateRequest.vendor_id as optional). Integration finding (E.3 live
    # pass): this was still `Mapped[int]` (NOT NULL) here, so that exact code path raised a raw
    # sqlite3.IntegrityError instead of the clean draft PO it was designed to produce — reproduced
    # live via the chat "approve and generate the PO" flow against a quote-less feasibility run.
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    po_number: Mapped[str] = mapped_column(String, nullable=False)
    item_description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price_myr: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_price_myr: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    project: Mapped["Project"] = relationship(back_populates="purchase_orders")


class RFQ(Base):
    """A request-for-quote sent to one vendor by email. One procurement request
    fans out into several RFQ rows sharing a batch_id; vendor replies are matched
    back by the token embedded in the email subject."""

    __tablename__ = "rfqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(String, nullable=False)  # groups one request's RFQs
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # per-vendor correlation
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    manager_phone: Mapped[str] = mapped_column(String, nullable=False)
    item_description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String, default="sent")  # sent | quoted | declined | expired
    quote_unit_price_myr: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    quote_delivery_days: Mapped[int | None] = mapped_column(nullable=True)
    quote_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    quoted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String, default="idle")
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


# ============================================================================
# ARD §3.3 — new tables for the feasibility/procurement/chat platform layer.
# Additive only; nothing above this line changes shape for existing rows.
# ============================================================================


class Component(Base):
    """A catalogued module or inverter — seeded from the vendored CEC CSVs
    (ARD D4) plus anything captured from a parsed supplier quote whose model
    wasn't in the catalog (source='parsed_quote')."""

    __tablename__ = "components"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # module | inverter
    manufacturer: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[int | None] = mapped_column(nullable=True)

    # module fields
    rated_wp: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    vmp: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    voc: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    imp: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    isc: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    temp_coeff_voc_pct_per_c: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    efficiency_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    cell_tech: Mapped[str | None] = mapped_column(String, nullable=True)
    area_m2: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)

    # inverter fields
    ac_rating_kw: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    max_dc_input_kw: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    mppt_min_v: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    mppt_max_v: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    max_dc_voltage_v: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    max_input_current_per_mppt_a: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    mppt_count: Mapped[int | None] = mapped_column(nullable=True)
    phase: Mapped[str | None] = mapped_column(String, nullable=True)  # single | three
    euro_efficiency_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    has_anti_islanding: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # shared
    datasheet_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, default="CEC")  # CEC | manufacturer | parsed_quote
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class SupplierQuote(Base):
    """One parsed vendor PDF/image quote (ARD §3.3 / §5.4)."""

    __tablename__ = "supplier_quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    supplier_name_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="MYR")
    fx_rate_to_myr: Mapped[float] = mapped_column(Numeric(8, 4), default=1.0)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    parse_status: Mapped[str] = mapped_column(String, default="parsed")  # parsed | partial | failed
    parse_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_json: Mapped[dict] = mapped_column(JSON, default=dict)
    subtotal_myr: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    line_items: Mapped[list["QuoteLineItem"]] = relationship(back_populates="quote")


class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("supplier_quotes.id"))
    line_no: Mapped[int] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(String, default="unknown")  # module|inverter|battery|bos|service|unknown
    manufacturer: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_price_myr: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    line_total_myr: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    rated_wp: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    price_per_wp_myr: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    warranty_years: Mapped[int | None] = mapped_column(nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(nullable=True)
    bnef_tier1: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tier_match_name: Mapped[str | None] = mapped_column(String, nullable=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)

    quote: Mapped["SupplierQuote"] = relationship(back_populates="line_items")


class FeasibilityRun(Base):
    __tablename__ = "feasibility_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    quote_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_quotes.id"), nullable=True)
    module_component_id: Mapped[int | None] = mapped_column(ForeignKey("components.id"), nullable=True)
    inverter_component_id: Mapped[int | None] = mapped_column(ForeignKey("components.id"), nullable=True)
    system_type: Mapped[str] = mapped_column(String, default="on_grid")
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[dict] = mapped_column(JSON, default=dict)  # the full serialised DesignReport (ARD §5.3)
    status: Mapped[str] = mapped_column(String, default="pass")  # pass | warn | fail
    confidence_score: Mapped[int | None] = mapped_column(nullable=True)
    confidence_band: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_key: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, default="")
    cards: Mapped[list] = mapped_column(JSON, default=list)
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    tool_trace: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
