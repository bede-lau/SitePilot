"""Real RFQ email loop: send RFQs over SMTP, read vendor quote replies over IMAP.

Uses the Python stdlib (smtplib/imaplib/email) run in a thread pool so the async
event loop is never blocked. Activates only when SMTP is configured in settings;
callers should check ``settings.email_enabled`` and fall back to the simulated
quote path otherwise.

Correlation: every outbound RFQ subject carries a token like ``[FB-<token>]``.
Vendor replies keep that token in the subject (standard "Re:" behaviour), so the
poller can match a reply back to the exact RFQ row regardless of sender address.
"""
import asyncio
import email
import imaplib
import logging
import re
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

from app.config import settings

logger = logging.getLogger("fieldbot.email")

TOKEN_RE = re.compile(r"\[FB-([A-Za-z0-9]+)\]")


def subject_token(token: str) -> str:
    return f"[FB-{token}]"


def _send_sync(
    to_email: str,
    subject: str,
    body: str,
    attachment: tuple[bytes, str] | None = None,
) -> None:
    msg = EmailMessage()
    msg["From"] = settings.effective_smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    if attachment:
        attachment_bytes, filename = attachment
        msg.add_attachment(attachment_bytes, maintype="application", subtype="pdf", filename=filename)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


async def send_rfq_email(to_email: str, subject: str, body: str) -> None:
    """Send one RFQ. Raises on SMTP failure so the caller can report it."""
    await asyncio.to_thread(_send_sync, to_email, subject, body)
    logger.info("RFQ email sent to=%s subject=%r", to_email, subject)


async def send_email_with_attachment(
    to_email: str, subject: str, body: str, attachment_bytes: bytes, attachment_filename: str
) -> None:
    """Send an email with a single PDF attachment (invoice-to-customer, PO-to-vendor).
    Raises on SMTP failure so the caller can decide whether to roll back or just log it —
    callers should only invoke this when settings.email_enabled is True."""
    await asyncio.to_thread(_send_sync, to_email, subject, body, (attachment_bytes, attachment_filename))
    logger.info("email with attachment sent to=%s subject=%r filename=%s", to_email, subject, attachment_filename)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(
                part.get("Content-Disposition", "")
            ):
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return str(msg.get_payload())


def _fetch_unseen_sync() -> list[dict]:
    """Return unseen replies that carry an RFQ token. Marks them seen as a side effect."""
    host = settings.effective_imap_host
    conn = imaplib.IMAP4_SSL(host, settings.imap_port)
    out: list[dict] = []
    try:
        conn.login(settings.effective_imap_user, settings.effective_imap_password)
        conn.select("INBOX")
        status, data = conn.search(None, "UNSEEN")
        if status != "OK" or not data or not data[0]:
            return out
        for num in data[0].split():
            status, msg_data = conn.fetch(num, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = str(msg.get("Subject", ""))
            match = TOKEN_RE.search(subject)
            if not match:
                continue  # not an RFQ reply — leave for the human, but we already consumed UNSEEN
            if not subject.strip().lower().startswith("re:"):
                # Our own outbound RFQ, not a reply. Gmail "+alias" addressing means
                # RFQs we send to vendor.contact_email (an alias of this same mailbox)
                # land right back in this INBOX — without this check they'd be
                # misread as an instant vendor "decline" with no price.
                continue
            out.append(
                {
                    "token": match.group(1),
                    "from": parseaddr(str(msg.get("From", "")))[1],
                    "subject": subject,
                    "body": _extract_body(msg),
                }
            )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        conn.logout()
    return out


async def fetch_quote_replies() -> list[dict]:
    """Poll IMAP for new vendor replies tagged with an RFQ token."""
    return await asyncio.to_thread(_fetch_unseen_sync)
