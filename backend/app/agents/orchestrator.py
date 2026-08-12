"""Conversational co-pilot for the site manager.

This is the LLM-driven branch of the hybrid router. The deterministic fast-path
(photos -> inspection, YES/NO -> confirm) is handled in the webhook before we ever
get here; everything else — questions about projects, vendors, invoices, POs, and
ad-hoc procurement requests phrased in natural language — lands in this orchestrator.

The model is given a set of tools (see app/agents/tools.py) and decides which to
call. It is told its domain is solar site operations and to decline anything
outside it. No DB numbers are ever invented: the model can only report what the
tools return.
"""
import json
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.agents.tools import TOOL_FUNCTIONS
from app.models.models import ConversationSession
from app.services.llm_client import get_client

logger = logging.getLogger("fieldbot.orchestrator")

MAX_TOOL_ROUNDS = 5
# How many past user/assistant turns to replay so follow-ups like "yes" keep
# the question they're answering — tool calls themselves aren't replayed.
MAX_HISTORY_TURNS = 6

SYSTEM_PROMPT = (
    "You are FieldBot, a WhatsApp co-pilot for a solar installation site manager in Malaysia. "
    "You help with site projects, inspection reports, progress-claim invoices, vendors, "
    "purchase orders, and material procurement. You are talking over WhatsApp, so keep replies "
    "short and skimmable — a few lines, plain text, light emoji only where it helps.\n\n"
    "Use the tools to answer. Never invent project names, numbers, prices, or statuses — if a "
    "tool doesn't return it, say you don't have it. Money is in Malaysian Ringgit; format as "
    "'RM 12,000'.\n\n"
    "To raise a material/procurement request, call start_procurement with the EXACT quantity and "
    "item the manager typed — never round, guess, or substitute a different number. Then relay its "
    "message_to_user text to the manager VERBATIM, character for character — do not paraphrase it "
    "or restate the quantity/vendor count in your own words. The RFQ runs in the background and "
    "quotes arrive later as separate messages.\n\n"
    "CRITICAL: never claim you have started an RFQ, ordered something, drafted an invoice, or sent "
    "anything unless you have actually called the matching tool in THIS reply. Earlier messages in "
    "the conversation that say an action was done are NOT proof it happened — if the manager asks "
    "again, call the tool again. Saying 'I've started the RFQ' without calling start_procurement is "
    "a serious error.\n\n"
    "Stay strictly within solar site operations. If asked about anything outside that domain "
    "(general knowledge, trivia, coding, current events, math, etc.), you MUST refuse. Your reply "
    "must NOT contain the answer or any part of it — even if you know it. Reply with exactly this "
    "and nothing else: \"That's outside what I handle — I'm just your site ops co-pilot. Ask me "
    "about projects, inspections, invoices, vendors or procurement. 🙂\""
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "List solar projects with their client, location, region, panel count, contract value and status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Optional filter, e.g. 'active'."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project",
            "description": "Get one project's details plus counts of its inspections, invoices and purchase orders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project name (partial ok) or numeric id."}
                },
                "required": ["project"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_inspections",
            "description": "List recent site inspection reports, optionally filtered to one project.",
            "parameters": {
                "type": "object",
                "properties": {"project": {"type": "string", "description": "Optional project name or id."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_invoices",
            "description": "List recent progress-claim invoice drafts, optionally filtered to one project.",
            "parameters": {
                "type": "object",
                "properties": {"project": {"type": "string", "description": "Optional project name or id."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_purchase_orders",
            "description": "List recent purchase orders, optionally filtered to one project.",
            "parameters": {
                "type": "object",
                "properties": {"project": {"type": "string", "description": "Optional project name or id."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_vendors",
            "description": "List approved vendors, optionally filtered by region ('north', 'central', 'south').",
            "parameters": {
                "type": "object",
                "properties": {"region": {"type": "string", "description": "Optional region filter."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_procurement",
            "description": "Send a request-for-quote to matching vendors for a material the site needs. Use when the manager wants to order/buy/procure something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_description": {"type": "string", "description": "What is being requested, e.g. 'solar panels'."},
                    "quantity": {"type": "integer", "description": "How many units."},
                    "region": {"type": "string", "description": "Region to source from ('north'/'central'/'south'), or omit."},
                },
                "required": ["item_description", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_invoice",
            "description": "Manually create a progress-claim invoice draft for a project at a given completion percentage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project name or id."},
                    "claim_percentage": {"type": "number", "description": "Completion percent to claim, 0-100."},
                },
                "required": ["project", "claim_percentage"],
            },
        },
    },
]

CAPABILITY_REPLY = (
    "Hi, I'm FieldBot — your site ops co-pilot. I can help with:\n"
    "• Projects, inspections & progress claims\n"
    "• Vendors & purchase orders\n"
    "• Ordering materials (just tell me what and how many)\n\n"
    "Send site photos for an inspection, or ask me something like "
    "\"show active projects\" or \"order 15 panels for Penang\"."
)


# A procurement *action* request (not just chit-chat about POs). Qwen will sometimes
# narrate "I've started the RFQ…" without actually calling start_procurement — worse,
# replayed history full of those fake confirmations reinforces the habit. When the
# manager clearly asks to order/procure, we force the tool call so a real RFQ fires.
_PROCURE_WORD = re.compile(r"\b(rfq|procure|procurement|purchase\s*order|p\.?o\.?|order|buy|purchase)\b", re.IGNORECASE)
_ACTION_WORD = re.compile(r"\b(make|create|send|raise|start|issue|place|order|procure|buy|get|need|want)\b", re.IGNORECASE)


def _wants_procurement(body: str) -> bool:
    text = body or ""
    if re.search(r"\border\s+\d", text, re.IGNORECASE):  # "order 84 ..."
        return True
    return bool(_PROCURE_WORD.search(text) and _ACTION_WORD.search(text))


async def run_orchestrator(
    db: AsyncSession, session: ConversationSession, from_number: str, body: str
) -> str:
    """Run the tool-calling loop and return the reply text to send over WhatsApp."""
    if not settings.llm_api_key:
        # Without an LLM there's no tool reasoning; give a useful capability menu
        # instead of a dead-end greeting.
        return CAPABILITY_REPLY

    client = get_client()
    history = (session.context or {}).get("history", [])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": body},
    ]
    # Force start_procurement on the first round for clear ordering requests so the
    # model can't satisfy them with a fabricated text confirmation.
    force_procurement = _wants_procurement(body)

    for round_index in range(MAX_TOOL_ROUNDS):
        if force_procurement and round_index == 0:
            tool_choice = {"type": "function", "function": {"name": "start_procurement"}}
        else:
            tool_choice = "auto"
        response = await client.chat.completions.create(
            model=settings.llm_text_model,
            messages=messages,
            tools=TOOLS,
            tool_choice=tool_choice,
        )
        msg = response.choices[0].message
        if not msg.tool_calls:
            reply = (msg.content or CAPABILITY_REPLY).strip()
            await _save_turn(db, session, history, body, reply)
            return reply

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        for tc in msg.tool_calls:
            fn = TOOL_FUNCTIONS.get(tc.function.name)
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            logger.info("tool call name=%s args=%s body=%r", tc.function.name, args, body)
            if fn is None:
                result = {"error": f"unknown tool {tc.function.name}"}
            else:
                try:
                    result = await fn(db, from_number, **args)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("tool %s failed", tc.function.name)
                    result = {"error": f"tool {tc.function.name} failed: {exc}"}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

    # Ran out of tool rounds — ask the model for a final answer with what it has.
    final = await client.chat.completions.create(model=settings.llm_text_model, messages=messages)
    reply = (final.choices[0].message.content or CAPABILITY_REPLY).strip()
    await _save_turn(db, session, history, body, reply)
    return reply


async def _save_turn(
    db: AsyncSession,
    session: ConversationSession,
    history: list[dict],
    user_body: str,
    reply: str,
) -> None:
    """Append this exchange to the session's rolling history (no tool-call detail)."""
    updated = [*history, {"role": "user", "content": user_body}, {"role": "assistant", "content": reply}]
    updated = updated[-MAX_HISTORY_TURNS * 2 :]
    session.context = {**(session.context or {}), "history": updated}
    await db.commit()
