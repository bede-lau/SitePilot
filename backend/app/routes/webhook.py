import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.inspection import run_inspection
from app.agents.invoicing import cancel_invoice, confirm_invoice, start_invoice_draft
from app.agents.orchestrator import run_orchestrator
from app.agents.procurement import cancel_purchase_order, confirm_purchase_order, start_po_request
from app.agents.router import route_intent
from app.database import get_db
from app.services.messaging import send_message
from app.services.sessions import get_or_create_session

logger = logging.getLogger("fieldbot.webhook")

router = APIRouter()


def _parse_update(update: dict) -> tuple[str, str, list[str]]:
    """Pull (chat_id, text, photo file_ids) out of a Telegram update.

    A message may carry a text body, a photo (sent in several resolutions — we
    take the largest), or a document whose mime type is an image. Caption text
    that rides along with a photo is treated as the body."""
    message = update.get("message") or update.get("edited_message") or {}
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text") or message.get("caption") or ""

    file_ids: list[str] = []
    photo = message.get("photo")
    if photo:  # array of PhotoSize, ascending; last is the highest resolution
        file_ids.append(photo[-1]["file_id"])
    document = message.get("document")
    if document and str(document.get("mime_type", "")).startswith("image/"):
        file_ids.append(document["file_id"])

    return chat_id, text, file_ids


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    update = await request.json()
    from_number, body, file_ids = _parse_update(update)
    has_media = bool(file_ids)

    if not from_number:
        return {"ok": True}  # non-message update (e.g. status); nothing to do

    logger.info("incoming message from=%s body=%r num_media=%s", from_number, body, len(file_ids))

    session = await get_or_create_session(db, from_number)
    intent = route_intent(body, has_media, session)
    logger.info("routed intent=%s from=%s", intent, from_number)

    if intent == "inspection":
        send_message(from_number, "Analyzing your site photos… 🔍")
        await run_inspection(db, session, from_number, file_ids)
    elif intent == "confirm":
        await confirm_purchase_order(db, session, from_number)
    elif intent == "cancel":
        await cancel_purchase_order(db, session, from_number)
    elif intent == "confirm_clarify":
        send_message(from_number, "Please reply YES to confirm or NO to cancel.")
    elif intent == "confirm_invoice":
        await confirm_invoice(db, session, from_number)
    elif intent == "cancel_invoice":
        await cancel_invoice(db, session, from_number)
    elif intent == "invoice_confirm_clarify":
        send_message(from_number, "Please reply YES to email the customer, or NO to leave it as a draft.")
    elif intent == "choose_invoice":
        await start_invoice_draft(db, session, from_number)
    elif intent == "choose_po":
        session.state = "awaiting_po_request"
        await db.commit()
        send_message(from_number, "What material and how many units do you need?")
    elif intent == "followup_clarify":
        send_message(from_number, "Reply \"invoice\" to draft an invoice, or \"po\" to send a purchase order.")
    elif intent == "po_request":
        await start_po_request(db, session, from_number, body)
    else:  # orchestrator — natural-language co-pilot (Q&A + procurement requests)
        reply = await run_orchestrator(db, session, from_number, body)
        send_message(from_number, reply)

    return {"ok": True}
