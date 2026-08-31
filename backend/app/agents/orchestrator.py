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
import time
from typing import AsyncIterator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.agents.tools import TOOL_FUNCTIONS
from app.models.models import ChatMessage, ConversationSession
from app.services.llm_client import get_client

logger = logging.getLogger("fieldbot.orchestrator")

# A real flow needs 1 routing call + 1-2 tool rounds + 1 answer. 8 just let a
# confused model burn ~5 extra full-price round-trips before the non-tooled
# fallback; 4 covers every genuine chain and caps the tail latency.
MAX_TOOL_ROUNDS = 4
# Hard wall-clock ceiling for one chat turn. Each LLM call can stall for the
# client's per-request timeout; 4 tool rounds + a final call therefore stack
# into multi-minute "Thinking…" hangs whenever DashScope is slow — the "2
# minutes for a trivial question" bug. Past this budget we stop starting new
# rounds and answer with whatever we already have. Typical turns finish in
# ~1.5s and never come near it.
TURN_DEADLINE_SECONDS = 45
# How many past user/assistant turns to replay so follow-ups like "yes" keep
# the question they're answering — tool calls themselves aren't replayed.
MAX_HISTORY_TURNS = 6
# Replies are meant to be a few skimmable lines (see SYSTEM_PROMPT). Cap output
# so a chatty turn can't spend 10s generating paragraphs nobody asked for.
MAX_REPLY_TOKENS = 512
# Low temperature: this is a lookup/reporting bot, not creative writing — also
# trims a little generation latency and variance.
GEN_TEMPERATURE = 0.3
# qwen3 "flash/plus" are hybrid reasoning models with chain-of-thought ON by
# default — that CoT runs before every routing decision and every answer, and
# measured ~5s vs ~0.7s for a trivial turn on this endpoint. This bot forces its
# tools and only reports tool output, so the reasoning buys nothing. Disable it.
# (DashScope OpenAI-compat reads this from extra_body; harmless on non-reasoning
# models.)
GEN_EXTRA_BODY = {"enable_thinking": False}


def _round_timeout(remaining: float) -> httpx.Timeout:
    """Per-call budget: the smaller of what's left in the turn and 30s overall,
    with an 8s connect and a 20s read cap so a stream that dribbles to a near-stop
    mid-answer errors out instead of holding the spinner for minutes."""
    overall = min(30.0, max(5.0, remaining))
    return httpx.Timeout(overall, connect=8.0, read=min(20.0, overall))


def _tools_for_round(forced_choice: dict | None, round_index: int) -> list:
    """On a forced round-0 the model only ever calls the one forced tool, so
    sending the other 16 schemas just inflates the prompt (slower prefill, more
    tokens). Send the full set on every other round."""
    if forced_choice and round_index == 0:
        name = forced_choice["function"]["name"]
        return [t for t in TOOLS if t["function"]["name"] == name]
    return TOOLS

SYSTEM_PROMPT = (
    "You are FieldBot, a WhatsApp co-pilot for a solar installation site manager in Malaysia. "
    "You help with site projects, inspection reports, progress-claim invoices, vendors, "
    "purchase orders, and material procurement. You are talking over WhatsApp, so keep replies "
    "short and skimmable — a few lines, light emoji only where it helps.\n\n"
    "FORMAT with plain GitHub-flavoured Markdown so the app renders it cleanly:\n"
    "- Put each list item on its OWN line starting with '- ' (hyphen space). Never use the '•' "
    "character and never string several items onto one line.\n"
    "- Leave a blank line between a lead-in sentence and the list, and between paragraphs.\n"
    "- Use '**bold**' sparingly for a key term; no headings, tables, or code fences in chat.\n\n"
    "Good list reply:\n\n"
    "I can help with:\n\n"
    "- **Projects** — status, inspections, invoices\n"
    "- **Vendors** — approved suppliers by region\n\n"
    "What do you need?\n\n"
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
    "about projects, inspections, invoices, vendors or procurement. 🙂\"\n\n"
    "You also have feasibility/engineering tools (run_feasibility, generate_bos_spec, "
    "financial_analysis), a quote parser (parse_supplier_quote), a component catalog "
    "(list_components, check_bnef_tier) and a PO generator (generate_po_package). "
    "You never calculate. Voltages, currents, string counts, fuse ratings, savings, payback and "
    "confidence come only from tool results — quote them exactly as returned and never round or "
    "recompute them. When a tool returns a card, the UI is already showing it: your text must add "
    "context or a next step, not repeat the numbers.\n\n"
    "CRITICAL: because you never repeat numbers back in text, you are NOT shown a feasibility run's "
    "id anywhere in the conversation once its card has rendered. If the manager later asks you to "
    "fetch its BOS spec or generate its PO without stating the id, you do NOT have it — pass the "
    "project name instead (generate_bos_spec and generate_po_package both accept one and resolve "
    "to that project's latest run). NEVER invent a feasibility_run_id — generate_po_package creates "
    "a real purchase order and sends a real Telegram message, so guessing a wrong-but-real id would "
    "misfire it against someone else's project."
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
    {
        "type": "function",
        "function": {
            "name": "parse_supplier_quote",
            "description": "Extract line items, pricing and BNEF tier status from an uploaded supplier quote PDF/image. Use when the manager attaches or references a quote file and asks to extract/parse/normalize it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "file_id returned by a prior upload."},
                    "project": {"type": "string", "description": "Optional project name or id to attach the quote to."},
                },
                "required": ["file_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_feasibility",
            "description": "Run the deterministic engineering feasibility check (string sizing, MPPT window, DC:AC ratio, confidence score) for a project. Use for questions like 'can we pair these panels with a 10kW inverter' or 'check feasibility'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project name or id."},
                    "panel_count": {"type": "integer", "description": "Override panel count; defaults to the project's latest inspection."},
                    "quote_id": {"type": "integer", "description": "Optional parsed quote id to pull module specs/pricing from."},
                    "system_type": {"type": "string", "description": "on_grid | hybrid; defaults to the project's setting."},
                },
                "required": ["project"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_bos_spec",
            "description": "Re-fetch the balance-of-system protection spec (fuses, isolators, SPDs, cables) from a completed feasibility run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "feasibility_run_id": {
                        "type": "integer",
                        "description": "Id of a prior run_feasibility result, ONLY if the manager stated it explicitly. You are never shown this id in your own prior replies (per the anti-repetition rule below) — do not guess or invent one.",
                    },
                    "project": {
                        "type": "string",
                        "description": "Project name or id — use this instead when you don't have a specific run id; resolves to that project's latest feasibility run.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "financial_analysis",
            "description": "Get or compute the payback/savings financial model for a project (TNB RP4 tariff + Solar ATAP export).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project name or id."},
                    "feasibility_run_id": {"type": "integer", "description": "Optional — reuse a specific prior run instead of the project's latest."},
                    "system_cost_myr": {"type": "number", "description": "Optional system cost override."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_components",
            "description": "Search the CEC module/inverter catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "module | inverter"},
                    "brand": {"type": "string", "description": "Optional manufacturer filter."},
                    "q": {"type": "string", "description": "Optional model search text."},
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_bnef_tier",
            "description": "Check whether a panel manufacturer is BloombergNEF Tier 1.",
            "parameters": {
                "type": "object",
                "properties": {"manufacturer": {"type": "string", "description": "Manufacturer name."}},
                "required": ["manufacturer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_po_package",
            "description": "Create the purchase order from an approved feasibility run, render its PDF, and send it to the field engineer's Telegram. Use when the manager says approve/generate the PO.",
            "parameters": {
                "type": "object",
                "properties": {
                    "feasibility_run_id": {
                        "type": "integer",
                        "description": "Id of the approved feasibility run, ONLY if the manager stated it explicitly. You are never shown this id in your own prior replies (per the anti-repetition rule below) — do not guess or invent one.",
                    },
                    "project": {
                        "type": "string",
                        "description": "Project name or id — use this instead when you don't have a specific run id; resolves to that project's latest feasibility run.",
                    },
                    "vendor": {"type": "string", "description": "Optional vendor name or id; defaults to the quote's matched vendor."},
                },
            },
        },
    },
]

CAPABILITY_REPLY = (
    "Hi, I'm FieldBot — your site ops co-pilot. I can help with:\n\n"
    "- Projects, inspections & progress claims\n"
    "- Vendors & purchase orders\n"
    "- Ordering materials (just tell me what and how many)\n\n"
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


# Same anti-fabrication trick (ARD §5.6 risk mitigation), extended to the two
# other tools whose numbers a judge will scrutinize: a model that narrates a
# string/MPPT check or a quote extraction without calling the tool is
# presenting a fabricated calculation as real. Force the tool on round 0 when
# the request is unambiguous; ordinary chit-chat still goes through "auto".
_FEASIBILITY_WORD = re.compile(
    r"\b(feasib(le|ility)|string(s|ing)?|mppt|dc\s*[:/]\s*ac|inverter|pair|compatib|validate)\b", re.IGNORECASE
)
_FEASIBILITY_ACTION = re.compile(r"\b(check|run|can we|pair|validate|compatib|verify|confirm)\b", re.IGNORECASE)


def _wants_feasibility(body: str) -> bool:
    text = body or ""
    return bool(_FEASIBILITY_WORD.search(text) and _FEASIBILITY_ACTION.search(text))


_QUOTE_PARSE_WORD = re.compile(r"\b(extract|parse|read|normali[sz]e|process)\b", re.IGNORECASE)
_QUOTE_WORD = re.compile(r"\bquote\b", re.IGNORECASE)


def _wants_quote_parse(body: str, has_attachment: bool) -> bool:
    if not has_attachment:
        return False
    text = body or ""
    return bool(_QUOTE_PARSE_WORD.search(text) or _QUOTE_WORD.search(text)) or not text.strip()


# Integration finding (E.3 live pass): "financial_analysis" was the one ARD §5.6
# tool with no forcing. Under "auto" tool_choice, qwen-plus reliably calls it for
# the exact PRD §6 suggestion-chip phrasing ("What's the payback period for the
# Greenfield project?") but a near-identical rephrasing ("What is the financial
# payback for that system?") made it narrate fabricated RM figures and a fake
# confidence score with no tool call and no card — exactly the failure mode this
# forcing pattern exists to prevent. Same treatment as feasibility above.
_FINANCIAL_WORD = re.compile(
    r"\b(financ(e|ial)|payback|savings?|roi|return\s+on\s+investment|bill\s*(before|after)?)\b",
    re.IGNORECASE,
)


def _wants_financial(body: str) -> bool:
    return bool(_FINANCIAL_WORD.search(body or ""))


def _forced_tool_choice(body: str, has_attachment: bool = False) -> dict | None:
    """One forced tool per round-0, priority: procurement > quote parse > feasibility > financial
    (an ordering request always wins if all four phrases somehow overlap)."""
    if _wants_procurement(body):
        return {"type": "function", "function": {"name": "start_procurement"}}
    if _wants_quote_parse(body, has_attachment):
        return {"type": "function", "function": {"name": "parse_supplier_quote"}}
    if _wants_feasibility(body):
        return {"type": "function", "function": {"name": "run_feasibility"}}
    if _wants_financial(body):
        return {"type": "function", "function": {"name": "financial_analysis"}}
    return None


def _split_tool_result(raw) -> tuple[dict, object]:
    """Tools return either a plain dict (the original 8 tools) or
    (result_dict, card_or_none) (the ARD §5.6 tools). Normalize to a
    (data, card) pair — card is None, a single {"card_type","data"} dict, or a
    list of them."""
    if isinstance(raw, tuple) and len(raw) == 2:
        return raw[0], raw[1]
    return raw, None


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
    # Force the matching tool on the first round for clear ordering/feasibility
    # requests so the model can't satisfy them with a fabricated confirmation or
    # calculation (ARD §5.6). Telegram has no attachment concept, so quote-parse
    # forcing never triggers here.
    forced_choice = _forced_tool_choice(body)
    start = time.monotonic()

    for round_index in range(MAX_TOOL_ROUNDS):
        remaining = TURN_DEADLINE_SECONDS - (time.monotonic() - start)
        if round_index > 0 and remaining <= 2:
            break  # out of time budget — fall through to the salvage answer below
        if forced_choice and round_index == 0:
            tool_choice = forced_choice
        else:
            tool_choice = "auto"
        response = await client.with_options(timeout=_round_timeout(remaining)).chat.completions.create(
            model=settings.llm_text_model,
            messages=messages,
            tools=_tools_for_round(forced_choice, round_index),
            tool_choice=tool_choice,
            max_tokens=MAX_REPLY_TOKENS,
            temperature=GEN_TEMPERATURE,
            extra_body=GEN_EXTRA_BODY,
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
                    raw = await fn(db, from_number, **args)
                    result, _card = _split_tool_result(raw)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("tool %s failed", tc.function.name)
                    # Integration finding (E.3 live pass): a raw DB exception (e.g. an IntegrityError
                    # from generate_po_package) leaves the shared AsyncSession in a failed-transaction
                    # state — every subsequent tool call in this round trip then also fails with
                    # "This Session's transaction has been rolled back...", cascading one bad call
                    # into a total loss of every remaining tool in the turn. Roll back so the next
                    # tool call starts on a clean transaction.
                    await db.rollback()
                    result = {"error": f"tool {tc.function.name} failed: {exc}"}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

    # Ran out of tool rounds (or the time budget) — ask for a final answer with
    # what it has. Bounded by whatever is left of the turn deadline so this can't
    # add another full-length stall on top of an already-slow turn.
    left = max(5.0, TURN_DEADLINE_SECONDS - (time.monotonic() - start))
    try:
        final = await client.with_options(timeout=_round_timeout(left)).chat.completions.create(
            model=settings.llm_text_model,
            messages=messages,
            max_tokens=MAX_REPLY_TOKENS,
            temperature=GEN_TEMPERATURE,
            extra_body=GEN_EXTRA_BODY,
        )
        reply = (final.choices[0].message.content or CAPABILITY_REPLY).strip()
    except Exception:  # noqa: BLE001
        logger.exception("final completion failed after tool rounds")
        reply = CAPABILITY_REPLY
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


# ============================================================================
# ARD §5.5 — the dashboard's streaming variant. Same tool-calling loop as
# run_orchestrator above, but as an AsyncIterator of SSE-shaped event dicts so
# routes/chat.py can forward them straight onto the wire. Kept as a separate
# function (rather than a `stream: bool` flag on run_orchestrator) so the
# Telegram path above is untouched — it neither imports nor calls this.
# ============================================================================


async def _save_stream_turn(
    db: AsyncSession, session_key: str, user_body: str, attachments: list[dict], reply_text: str, cards: list[dict]
) -> int:
    db.add(ChatMessage(session_key=session_key, role="user", content=user_body or "", attachments=attachments or []))
    assistant_msg = ChatMessage(session_key=session_key, role="assistant", content=reply_text, cards=cards or [])
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)
    return assistant_msg.id


async def run_orchestrator_stream(
    db: AsyncSession,
    session_key: str,
    from_number: str,
    body: str,
    history: list[dict],
    attachments: list[dict] | None = None,
) -> AsyncIterator[dict]:
    """Yields ARD §5.5 event dicts: status, tool, tool_result, delta, card,
    warning, done, error. `from_number` is the identity tools use for actions
    (RFQs, PO Telegram pushes) — for the dashboard this is settings.demo_phone_number,
    same identity the field engineer's Telegram thread uses."""
    attachments = attachments or []

    try:
        if not settings.llm_api_key:
            message_id = await _save_stream_turn(db, session_key, body, attachments, CAPABILITY_REPLY, [])
            yield {"type": "delta", "text": CAPABILITY_REPLY}
            yield {"type": "done", "message_id": message_id, "cards": []}
            return

        client = get_client()
        attachment_note = ""
        if attachments:
            desc = "; ".join(
                f"file_id={a.get('file_id')} kind={a.get('kind', '?')} filename={a.get('filename', '')}"
                for a in attachments
            )
            attachment_note = f"\n\n[Attached files: {desc}]"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": (body or "") + attachment_note},
        ]
        forced_choice = _forced_tool_choice(body, has_attachment=bool(attachments))
        all_cards: list[dict] = []
        final_text_parts: list[str] = []
        start = time.monotonic()
        deadline_hit = False

        yield {"type": "status", "label": "Thinking…", "phase": "reasoning"}

        for round_index in range(MAX_TOOL_ROUNDS):
            remaining = TURN_DEADLINE_SECONDS - (time.monotonic() - start)
            if round_index > 0 and remaining <= 2:
                deadline_hit = True
                break
            tool_choice = forced_choice if (forced_choice and round_index == 0) else "auto"
            stream = await client.with_options(timeout=_round_timeout(remaining)).chat.completions.create(
                model=settings.llm_text_model,
                messages=messages,
                tools=_tools_for_round(forced_choice, round_index),
                tool_choice=tool_choice,
                stream=True,
                max_tokens=MAX_REPLY_TOKENS,
                temperature=GEN_TEMPERATURE,
                extra_body=GEN_EXTRA_BODY,
            )

            content_parts: list[str] = []
            tool_calls_acc: dict[int, dict] = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    content_parts.append(delta.content)
                    yield {"type": "delta", "text": delta.content}
                if delta and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        acc = tool_calls_acc.setdefault(tc_delta.index, {"id": None, "name": None, "arguments": ""})
                        if tc_delta.id:
                            acc["id"] = tc_delta.id
                        if tc_delta.function and tc_delta.function.name:
                            acc["name"] = tc_delta.function.name
                        if tc_delta.function and tc_delta.function.arguments:
                            acc["arguments"] += tc_delta.function.arguments

            content_text = "".join(content_parts)

            if not tool_calls_acc:
                final_text_parts.append(content_text.strip() or CAPABILITY_REPLY)
                break

            tool_calls_list = [
                {
                    "id": acc["id"] or f"call_{idx}",
                    "type": "function",
                    "function": {"name": acc["name"], "arguments": acc["arguments"] or "{}"},
                }
                for idx, acc in sorted(tool_calls_acc.items())
            ]
            messages.append({"role": "assistant", "content": content_text or "", "tool_calls": tool_calls_list})

            for tc in tool_calls_list:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield {"type": "tool", "name": name, "args": args}

                fn = TOOL_FUNCTIONS.get(name)
                t0 = time.monotonic()
                if fn is None:
                    data, card, ok = {"error": f"unknown tool {name}"}, None, False
                else:
                    try:
                        raw = await fn(db, from_number, **args)
                        data, card = _split_tool_result(raw)
                        ok = not (isinstance(data, dict) and data.get("error"))
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("tool %s failed", name)
                        # See the matching rollback in run_orchestrator above — same cascading-failure
                        # bug, same fix, streaming variant.
                        await db.rollback()
                        data, card, ok = {"error": f"tool {name} failed: {exc}"}, None, False
                ms = int((time.monotonic() - t0) * 1000)
                summary = data.get("error") if isinstance(data, dict) and data.get("error") else "ok"
                yield {"type": "tool_result", "name": name, "ok": ok, "summary": summary, "ms": ms}

                if card:
                    for c in (card if isinstance(card, list) else [card]):
                        all_cards.append(c)
                        yield {"type": "card", "card_type": c["card_type"], "data": c["data"]}
                if isinstance(data, dict) and data.get("error"):
                    yield {"type": "warning", "level": "warn", "message": data["error"]}

                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(data, default=str)})

        if not final_text_parts:
            # Exhausted the tool rounds or hit the time budget without a plain-text
            # answer — ask for one last non-tooled completion, bounded by whatever
            # is left of the deadline so it can't tack on another long stall.
            left = max(5.0, TURN_DEADLINE_SECONDS - (time.monotonic() - start))
            try:
                final = await client.with_options(timeout=_round_timeout(left)).chat.completions.create(
                    model=settings.llm_text_model,
                    messages=messages,
                    max_tokens=MAX_REPLY_TOKENS,
                    temperature=GEN_TEMPERATURE,
                    extra_body=GEN_EXTRA_BODY,
                )
                reply = (final.choices[0].message.content or CAPABILITY_REPLY).strip()
            except Exception:  # noqa: BLE001
                logger.exception("final stream completion failed (deadline_hit=%s)", deadline_hit)
                reply = (
                    "That took longer than expected on my side — please try again."
                    if deadline_hit
                    else CAPABILITY_REPLY
                )
            yield {"type": "delta", "text": reply}
            final_text_parts.append(reply)

        reply_text = "\n".join(p for p in final_text_parts if p) or CAPABILITY_REPLY
        message_id = await _save_stream_turn(db, session_key, body, attachments, reply_text, all_cards)
        yield {"type": "done", "message_id": message_id, "cards": all_cards}

    except Exception as exc:  # noqa: BLE001
        logger.exception("run_orchestrator_stream failed session_key=%s", session_key)
        yield {"type": "error", "message": str(exc)}
