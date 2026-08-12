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
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
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
