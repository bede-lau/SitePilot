# FieldBot (SitePilot)

Telegram AI ops agent for solar site inspections and procurement. See `plan.txt` for the original architecture, `CLAUDE.md` for the current architecture (hybrid orchestrator + real email), `DEMO_CHECKLIST.md` for demo prep status.

## How messages are handled (hybrid router)

Incoming Telegram updates hit `POST /webhook/telegram` and route as:

- **Photos** → inspection agent (deterministic) — analyse, create report + invoice draft.
- **YES / NO while awaiting PO confirmation** → confirm/cancel handler (deterministic).
- **Everything else** → **LLM orchestrator** (`app/agents/orchestrator.py`): a tool-calling
  co-pilot that answers questions about projects, inspections, invoices, vendors and POs,
  and starts procurement requests. Off-domain questions are politely declined.

Only the two latency-sensitive, must-be-deterministic flows are keyword/state routed; natural
language goes to the orchestrator, so phrasing no longer has to match a fixed keyword list.

## Procurement: real email vs simulated

`start_procurement` (an orchestrator tool) emails RFQs to matching vendors over SMTP, then a
background poller reads vendor replies over IMAP, extracts the quote with the LLM, picks the
cheapest, and messages the manager to approve. Reply **YES** → Purchase Order created.

**If SMTP is not configured, this falls back to the simulated-quote flow** (8s delay, AI-generated
quote) so the demo works with zero email setup. See "Real RFQ email setup" below to turn it on.

## Running locally

Run each in its own terminal.

**Backend**
```
cd backend
venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

**ngrok tunnel** (exposes backend so Telegram can reach the webhook)
```
ngrok http 8000
```
If `ngrok` isn't found, restart your terminal — winget install needs a fresh shell to pick up PATH.

**Frontend**
```
cd frontend
npm run dev
```

## Telegram bot setup

1. **Create the bot:** message [@BotFather](https://t.me/BotFather) → `/newbot`, follow the prompts,
   copy the token it gives you. Put it in `backend/.env` as `TELEGRAM_BOT_TOKEN=...`.
2. **Find your chat id:** message [@userinfobot](https://t.me/userinfobot); it replies with your
   numeric id. Set `DEMO_PHONE_NUMBER=<that id>` in `backend/.env` so the seeded session binds your
   chat to the first project (lets you send inspection photos without a "which project?" prompt).
   Re-run the seed after changing it (`python -m app.seed`).
3. **Register the webhook:** after ngrok is up, point Telegram at it (one-time `curl`):
   ```
   curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<ngrok-id>.ngrok-free.app/webhook/telegram"
   ```
   Verify with `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"`.
4. Restart the backend, then DM your bot. To switch tunnels later, just re-run `setWebhook` with the
   new URL (and `deleteWebhook` to stop).

No daily message cap, no business verification — the Telegram Bot API is free.

## Real RFQ email setup (optional)

Procurement uses **simulated quotes** until you fill these in `backend/.env`. To send real RFQ
emails and read real vendor replies:

1. **Gmail (recommended for the demo):** turn on 2-step verification, then create an
   [App Password](https://myaccount.google.com/apppasswords). Use that 16-char password as
   `SMTP_PASSWORD` (not your normal Gmail password).
2. Set in `backend/.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=youraddress@gmail.com
   SMTP_PASSWORD=<app password>
   ```
   `IMAP_HOST`/`IMAP_USER`/`IMAP_PASSWORD` default to the Gmail/SMTP values, so they can stay blank.
3. **Vendor emails:** the seeded vendors (`app/seed.py`) use placeholder addresses
   (`ops@yspsolar.com`, etc.). Change them to addresses **you control** so you can reply to the
   RFQ and watch the quote come back. Re-run the seed after editing.
4. Restart the backend. On startup it logs either `RFQ inbox poller started` (email active) or
   `IMAP not configured … simulated quotes` (fallback).

**How correlation works:** each RFQ email subject carries a token like `[FB-ab12cd]`. Reply with
that token left in the subject (a normal "Re:" does this) and the poller matches your reply to the
right RFQ, extracts the price/lead-time with the LLM, and pings the manager to approve.

> Note: outbound Telegram sends fail gracefully (logged, no crash) instead of aborting the flow,
> so a transient send error never rolls back the agent's DB writes.

## Test photos

Drop test images into `backend/uploads/`, then run:
```
cd backend
venv\Scripts\python.exe test_photos.py
```
This calls `analyze_photo()` directly on every file in that folder and prints the vision LLM result, bypassing Telegram.
