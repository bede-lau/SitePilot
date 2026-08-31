from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InspectionCreate(BaseModel):
    project_id: int
    submitted_by_phone: str | None = None
    photo_urls: list[str] = []
    panels_detected: int | None = None
    panels_with_issues: int = 0
    issues: list = []
    completion_pct: float | None = None
    ai_analysis_raw: dict = {}


class InvoiceCreate(BaseModel):
    project_id: int
    inspection_report_id: int | None = None
    invoice_number: str
    claim_percentage: float | None = None
    claim_amount_myr: float | None = None


class PurchaseOrderCreate(BaseModel):
    project_id: int
    vendor_id: int
    po_number: str
    item_description: str
    quantity: int
    unit_price_myr: float | None = None
    total_price_myr: float | None = None


class ActivityEvent(BaseModel):
    event_type: str
    description: str
    entity_type: str | None = None
    entity_id: int | None = None
    timestamp: datetime


# ============================================================================
# ARD §5 — platform layer schemas (feasibility, quotes, chat).
# ============================================================================


class ComponentRef(BaseModel):
    """Either point at a catalogued component, or supply its specs inline
    (ARD §5.2 — used for both `module` and `inverter` on FeasibilityRequest)."""

    component_id: int | None = None
    manufacturer: str | None = None
    model: str | None = None
    rated_wp: float | None = None
    vmp: float | None = None
    voc: float | None = None
    imp: float | None = None
    isc: float | None = None
    temp_coeff_voc_pct_per_c: float | None = None
    # inverter-only inline fields
    ac_rating_kw: float | None = None
    max_dc_input_kw: float | None = None
    mppt_min_v: float | None = None
    mppt_max_v: float | None = None
    max_dc_voltage_v: float | None = None
    max_input_current_per_mppt_a: float | None = None
    mppt_count: int | None = None
    phase: str | None = None


class FeasibilityRequest(BaseModel):
    """ARD §5.2 — body of POST /api/feasibility/run."""

    project_id: int
    system_type: str | None = None  # on_grid | hybrid; defaults to the project's value
    panel_count: int | None = None  # defaults to the project's latest inspection count
    module: ComponentRef | None = None
    inverter: ComponentRef | None = None  # omit to auto-select
    quote_id: int | None = None
    monthly_consumption_kwh: float | None = None
    system_cost_myr: float | None = None
    budget_tier: str = "mid"  # entry | mid | premium
    backup_hours: float | None = None  # hybrid only
    critical_appliances: list[str] = []


class QuoteParseRequest(BaseModel):
    file_id: str
    project_id: int | None = None


class QuoteLineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_no: int
    category: str
    manufacturer: str | None = None
    model: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    unit_price_myr: float | None = None
    line_total_myr: float | None = None
    rated_wp: float | None = None
    price_per_wp_myr: float | None = None
    warranty_years: int | None = None
    lead_time_days: int | None = None
    bnef_tier1: bool | None = None
    tier_match_name: str | None = None
    flags: list = []


class SupplierQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None = None
    vendor_id: int | None = None
    supplier_name_raw: str | None = None
    source_filename: str | None = None
    source_url: str | None = None
    currency: str
    fx_rate_to_myr: float
    page_count: int | None = None
    parse_status: str
    parse_notes: str | None = None
    subtotal_myr: float | None = None
    created_at: datetime
    line_items: list[QuoteLineItemOut] = []


class PoGenerateRequest(BaseModel):
    feasibility_run_id: int
    vendor_id: int | None = None
    notify_telegram: bool = True


class ChatRequest(BaseModel):
    session_key: str
    message: str
    attachments: list[dict] = []
