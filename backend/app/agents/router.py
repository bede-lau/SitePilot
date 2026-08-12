import logging

from app.models.models import ConversationSession

logger = logging.getLogger("fieldbot.router")


def route_intent(body: str, has_media: bool, session: ConversationSession) -> str:
    """Hybrid routing. Only the latency-sensitive, must-be-deterministic flows are
    decided here by keyword/state; everything else goes to the LLM orchestrator.

    Deterministic fast-paths:
      - photos        -> inspection
      - YES/NO while awaiting a PO confirmation -> confirm/cancel/clarify

    Everything else -> orchestrator (project Q&A, procurement requests, etc.).
    Procurement is intentionally NOT keyword-routed anymore: the orchestrator's
    start_procurement tool handles ordering, so phrasing no longer has to match a
    fixed keyword list.
    """
    text = (body or "").strip().lower()

    if has_media:
        return "inspection"

    if session.state == "awaiting_procurement_confirm":
        if text in ("yes", "approve", "ok"):
            return "confirm"
        if text in ("no", "cancel"):
            return "cancel"
        return "confirm_clarify"

    if session.state == "awaiting_invoice_confirm":
        if text in ("yes", "approve", "ok"):
            return "confirm_invoice"
        if text in ("no", "cancel"):
            return "cancel_invoice"
        return "invoice_confirm_clarify"

    if session.state == "awaiting_followup_choice":
        if "invoice" in text:
            return "choose_invoice"
        if "po" in text or "purchase" in text or "order" in text or "material" in text:
            return "choose_po"
        return "followup_clarify"

    if session.state == "awaiting_po_request":
        return "po_request"

    return "orchestrator"
