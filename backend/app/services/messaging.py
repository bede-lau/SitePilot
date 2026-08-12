import logging

import httpx

from app.config import settings

logger = logging.getLogger("fieldbot.messaging")


def send_message(to: str, text: str) -> bool:
    """Send an outbound Telegram message. Returns True on success.

    A send failure (network, Telegram 4xx/5xx) is logged and swallowed rather
    than raised, so a messaging error never rolls back the agent's DB writes or
    aborts the rest of a flow. `to` is a Telegram chat id (as a string)."""
    if not settings.telegram_bot_token:
        logger.info("[telegram:stub] to=%s text=%r", to, text)
        return True

    try:
        resp = httpx.post(
            f"{settings.telegram_api_base}/sendMessage",
            json={"chat_id": to, "text": text},
            timeout=20,
        )
        resp.raise_for_status()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Telegram send failed to=%s", to)
        return False


def send_document(to: str, file_bytes: bytes, filename: str, caption: str | None = None) -> bool:
    """Send a PDF (or other file) as a Telegram document. Same swallow-and-log
    failure pattern as send_message — a failed upload must not abort the
    caller's DB writes."""
    if not settings.telegram_bot_token:
        logger.info("[telegram:stub] to=%s document=%s caption=%r", to, filename, caption)
        return True

    try:
        data = {"chat_id": to}
        if caption:
            data["caption"] = caption
        resp = httpx.post(
            f"{settings.telegram_api_base}/sendDocument",
            data=data,
            files={"document": (filename, file_bytes, "application/pdf")},
            timeout=30,
        )
        resp.raise_for_status()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Telegram document send failed to=%s filename=%s", to, filename)
        return False
