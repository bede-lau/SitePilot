import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.inspection import run_inspection
from app.agents.invoicing import cancel_invoice, confirm_invoice, start_invoice_draft
from app.agents.orchestrator import run_orchestrator
from app.agents.procurement import cancel_purchase_order, confirm_purchase_order, start_po_request
from app.agents.router import route_intent
from app.database import get_db
from app.services.media import download_telegram_media
from app.services.messaging import send_message
from app.services.sessions import get_or_create_session
from app.services.voice import transcribe

logger = logging.getLogger("fieldbot.webhook")

router = APIRouter()


def _parse_update(update: dict) -> tuple[str, str, list[str], str | None]:
    """Pull (chat_id, text, photo file_ids, voice_file_id) out of a Telegram update.

    A message may carry a text body, a photo (sent in several resolutions — we
    take the largest), a document whose mime type is an image, or a voice
    note/audio/video-note (ARD §8) — at most one of those is transcribed and
    fed into the router as the body. Caption text that rides along with a
    photo is treated as the body."""
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

    voice_file_id = None
    for key in ("voice", "audio", "video_note"):
        media = message.get(key)
        if media and media.get("file_id"):
            voice_file_id = media["file_id"]
            break

    return chat_id, text, file_ids, voice_file_id


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    update = await request.json()
    from_number, body, file_ids, voice_file_id = _parse_update(update)
    has_media = bool(file_ids)

    if not from_number:
        return {"ok": True}  # non-message update (e.g. status); nothing to do

    heard_prefix = ""
    if voice_file_id and not body:
        # ARD §8: getFile -> download (reuse services/media.py) -> transcribe ->
        # route the transcript through the normal router as the message body,
        # prefixed in the reply so the field engineer can confirm what was heard.
        # Integration finding (E.5 live pass): download_telegram_media raises
        # httpx.HTTPStatusError on any non-2xx Telegram response (expired file_id,
        # revoked bot token, a transient Telegram API hiccup) — reproduced live as
        # an unhandled 500 on this route, breaking the resilience contract every
        # other Telegram path in this app follows (messaging.send_message swallows
        # its own failures; this must too rather than dropping the whole webhook).
        try:
            audio_bytes = await download_telegram_media(voice_file_id)
            result = await transcribe(audio_bytes, "voice.ogg", "audio/ogg")
        except Exception:
            logger.exception("voice note download/transcribe failed from=%s", from_number)
            send_message(from_number, "Sorry, I couldn't fetch that voice note. Please try again or type it.")
            return {"ok": True}
        body = result.get("text", "") or ""
        if body:
            heard_prefix = f'\U0001F3A4 Heard: "{body}"\n\n'
            logger.info("voice note transcribed from=%s text=%r", from_number, body)
        else:
            send_message(from_number, "Sorry, I couldn't make out that voice note. Please try again or type it.")
            return {"ok": True}

    logger.info("incoming message from=%s body=%r num_media=%s voice=%s", from_number, body, len(file_ids), bool(voice_file_id))

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
        send_message(from_number, heard_prefix + reply)

    return {"ok": True}
