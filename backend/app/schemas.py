from datetime import datetime

from pydantic import BaseModel


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
