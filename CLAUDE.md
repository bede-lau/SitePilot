# FieldBot (SitePilot) — architecture notes for Claude

Telegram AI ops co-pilot for solar site managers. FastAPI backend, React/Vite frontend,
SQLite (async), Telegram Bot API, OpenAI-compatible LLM (currently Qwen via Dashscope).

`plan.txt` is the **original** hackathon plan (keyword router + simulated procurement). This file
documents what the code does **now** — it supersedes `plan.txt` where they differ.

## Message routing — hybrid

`backend/app/routes/webhook.py` (`POST /webhook/telegram`, parses the Telegram update JSON →
chat id as `from_number`, text/caption as body, largest `photo` size or image `document` as media
file_ids) → `app/agents/router.py::route_intent`:

| Input | Route | Handler |
|-------|-------|---------|
| Has photo(s) | `inspection` | `agents/inspection.py` (deterministic) |
| `yes`/`no` while `state == awaiting_procurement_confirm` | `confirm`/`cancel` | `agents/procurement.py` |
| other text while awaiting confirm | `confirm_clarify` | reply "YES/NO" |
| **anything else** | `orchestrator` | `agents/orchestrator.py` (LLM tool-calling) |

Only the two latency-sensitive, deterministic flows are keyword/state routed. **Procurement is no
longer keyword-routed** — the orchestrator's `start_procurement` tool handles ordering, so phrasing
is free-form.

## Orchestrator (`agents/orchestrator.py`)

LLM co-pilot with OpenAI-style function calling. Tools live in `agents/tools.py`
(`TOOL_FUNCTIONS` maps name → async fn taking `(db, from_number, **args)`):

- read: `list_projects`, `get_project`, `list_inspections`, `list_invoices`,
  `list_purchase_orders`, `find_vendors`
- act: `start_procurement` (RFQ flow), `draft_invoice`

Domain is locked to solar site ops via the system prompt; off-domain questions are refused without
answering. With no `LLM_API_KEY`, it returns a static capability menu (no tool reasoning possible).
Loop caps at `MAX_TOOL_ROUNDS = 5`.

## Procurement / RFQ email loop (`agents/procurement.py`)

`start_procurement_request(db, from_number, item, qty, region)`:
- **`settings.email_enabled` (SMTP set):** create one `RFQ` row per matching vendor (shared
  `batch_id`, unique `token`), email each via `services/email_client.send_rfq_email`.
- **else:** fall back to `run_procurement` background task (simulated 8s + AI quote).

Inbound: `services/rfq_poller.py` runs in the app lifespan when `settings.imap_enabled`. Every
`RFQ_POLL_SECONDS` it reads unseen token-tagged replies (`email_client.fetch_quote_replies`),
parses each with `llm_client.parse_quote_email`, and calls `process_quote_reply(token, parsed)`,
which only records that RFQ's quote/decline. The PO draft is presented **once**, by
`_finalize_batch`, only after every RFQ in the batch is no longer `sent` (all quoted/declined) —
picks the cheapest quote, sets `awaiting_procurement_confirm` with `pending_po`, Telegrams the
manager. If a vendor never replies, `check_stale_batches` (run every poll cycle) force-expires and
finalizes the batch after `RFQ_BATCH_TIMEOUT_SECONDS` (default 120s) using whatever quotes arrived.
**YES** → `confirm_purchase_order` creates the PO and expires the rest of the batch.

Correlation token format: subject contains `[FB-<token>]`; vendor "Re:" keeps it.

## Data model additions

`models/models.py::RFQ` — tracks each outbound RFQ + its quote (`batch_id`, `token`, `status`:
sent/quoted/declined/expired, quote fields). `reset_demo.py` clears it.

## Resilience notes

- `services/messaging.send_message(to, text)` (Telegram `sendMessage`) returns `bool` and
  **swallows send failures** (logs them); a failed send must not roll back DB writes or abort an
  agent flow. Inbound media is two-step: `services/media.download_telegram_media(file_id)` calls
  `getFile` then fetches from the Telegram file CDN.
- Stub paths (no `TELEGRAM_BOT_TOKEN` / no `LLM_API_KEY` / no SMTP) keep the app fully runnable for
  demos — outbound sends just log instead of hitting Telegram.

## Manual setup required

- **Telegram + LLM**: set `TELEGRAM_BOT_TOKEN` (from @BotFather) and `DEMO_PHONE_NUMBER` (your numeric
  Telegram chat id) in `backend/.env`; LLM is already set. Register the webhook via the Telegram
  `setWebhook` API pointed at `<public-url>/webhook/telegram`. See README "Telegram bot setup".
- **Real email** (optional — off by default): set `SMTP_*` in `backend/.env` (Gmail App Password),
  and point seeded vendor emails at addresses you control. See README "Real RFQ email setup".

## Running / testing

See `README.md`. Quick backend import/logic checks run via `venv\Scripts\python.exe -c "..."`;
set `PYTHONIOENCODING=utf-8` on Windows or emoji in replies crashes the console (not a code bug).
`python -m app.reset_demo` clears transactional rows between demo runs.
