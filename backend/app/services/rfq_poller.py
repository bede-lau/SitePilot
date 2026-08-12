"""Background loop that pulls vendor quote replies from the inbox.

Started from the app lifespan when IMAP is configured. Every poll it reads
unseen, token-tagged replies, asks the LLM to extract the quote, and hands each
off to the procurement agent which updates the RFQ and notifies the manager.
"""
import asyncio
import logging

from app.agents.procurement import check_stale_batches, process_quote_reply
from app.config import settings
from app.services.email_client import fetch_quote_replies
from app.services.llm_client import parse_quote_email

logger = logging.getLogger("fieldbot.rfq_poller")


async def _poll_once() -> None:
    replies = await fetch_quote_replies()
    for reply in replies:
        parsed = await parse_quote_email(reply["body"])
        logger.info("quote reply token=%s from=%s parsed=%s", reply["token"], reply.get("from"), parsed)
        await process_quote_reply(reply["token"], parsed)
    await check_stale_batches()


async def run_poller() -> None:
    logger.info("RFQ inbox poller started (every %ss)", settings.rfq_poll_seconds)
    while True:
        try:
            await _poll_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("RFQ poll cycle failed; will retry next interval")
        await asyncio.sleep(settings.rfq_poll_seconds)
