# SitePilot (FieldBot)

An agentic operating system for solar EPC contractors: a Telegram field interface for photo-based
panel counts and voice notes, plus a React dashboard where a project manager runs the whole
quote-to-PO workflow in one chat — parse a messy supplier PDF, validate string/inverter
compatibility against deterministic electrical formulas, model TNB RP4 + Solar ATAP payback, and
generate a signed-off Purchase Order sent straight back to the field engineer's Telegram.

See `plan.txt` for the original hackathon architecture, `CLAUDE.md` for how the code works today,
`ARD.md` for the full data model / API contract / design system this build implements, `New_PRD.md`
for the product spec and 4-minute demo script, and `DEMO_CHECKLIST.md` for demo prep status.

## What's in the box

| Surface | What it does |
|---|---|
| Telegram bot | Photo → CV panel count → inspection report + invoice draft. Voice note → transcribed (ElevenLabs) → fed into the same co-pilot. RFQ replies and PO delivery. |
| Dashboard `/` Command Center | Fleet KPIs, generation/spend trend, live activity feed, docked AI chat. |
| Dashboard `/feasibility` | Engineering workbench — pick project/module/inverter, run the deterministic string/MPPT/DC:AC/BOS engine, see the check matrix and confidence badge, click **Approve & Generate PO**. |
| Dashboard `/procurement` | Drop a supplier PDF/image, get parsed line items, RM/Wp, and BNEF Tier-1 status back. |
| Dashboard `/components` | Browse the seeded CEC module/inverter catalog. |
| Dashboard chat (any page) | Natural-language front end to all of the above — drag in a quote, ask "can we pair these panels with a 10kW Huawei inverter", ask for the payback period, approve the PO — via SSE streaming with rich cards, not just text. |

The one rule that shapes all of it (see `ARD.md` §1.1): **the LLM never does arithmetic.** Every
voltage, current, string count, fuse rating, RM figure and confidence score comes out of
`backend/app/engine/` — pure, unit-tested Python with no I/O. The LLM only reads messy documents
into structured JSON and decides which deterministic function to call.

## How messages are handled (hybrid router)

Incoming Telegram updates hit `POST /webhook/telegram` and route as:

- **Photos** → inspection agent (deterministic) — analyse, create report + invoice draft.
- **Voice note / audio / video note** → downloaded, transcribed (ElevenLabs, stub-safe with no key),
  then the transcript is fed into this same routing table as the message body — the reply is
  prefixed with what was heard so the field engineer can confirm.
- **YES / NO while awaiting PO confirmation** → confirm/cancel handler (deterministic).
- **Everything else** → **LLM orchestrator** (`app/agents/orchestrator.py`): a tool-calling
  co-pilot that answers questions about projects, inspections, invoices, vendors and POs, starts
  procurement requests, parses quotes, runs feasibility/BOS/financial analysis, and generates POs.
  Off-domain questions are politely declined. The dashboard chat (`POST /api/chat/stream`) shares
  this same orchestrator and tool set, streamed over SSE with rich cards instead of plain text.

Only the two latency-sensitive, must-be-deterministic flows are keyword/state routed; natural
language goes to the orchestrator, so phrasing no longer has to match a fixed keyword list.

## Procurement: real email vs simulated

`start_procurement` (an orchestrator tool) emails RFQs to matching vendors over SMTP, then a
background poller reads vendor replies over IMAP, extracts the quote with the LLM, picks the
cheapest, and messages the manager to approve. Reply **YES** → Purchase Order created.

**If SMTP is not configured, this falls back to the simulated-quote flow** (8s delay, AI-generated
quote) so the demo works with zero email setup. See "Real RFQ email setup" below to turn it on.

## Engineering, quote-parsing & financial engine

No manual setup beyond the existing `.env` keys — the calculation engine (`backend/app/engine/`)
is pure Python with no external dependency, and the CEC module/inverter catalog + BNEF Tier-1
registry are vendored CSVs loaded into the `components` table at seed time. Quote parsing reuses
the existing Dashscope key (`qwen-vl-max` vision) — no separate OCR key needed. See `ARD.md` §4 for
the formulas and §7 for the messy-quote fixture generator (`backend/scripts/generate_messy_quote.py`);
3 pre-generated fixtures already ship in `backend/uploads/quotes/` so the demo never depends on
running it live.

## Running locally

Run each in its own terminal. Always `export PYTHONIOENCODING=utf-8` first on Windows — the
console can't render the emoji some replies contain otherwise (not a code bug).

**Before a demo or recording:** re-seed so transactional data is fresh —
```
cd backend
rm fieldbot.db        # if it already exists
venv\Scripts\python.exe -m app.seed
```
Confirms: 5 projects, 6 vendors (exactly 1 BNEF Tier-2, exactly 1 quoting in USD), `components`
table with 45 modules + 37 inverters. `python -m app.reset_demo` clears transactional rows
(inspections, invoices, POs, quotes, feasibility runs, chat) between demo takes without touching
projects/vendors/components.

**Backend**
```
cd backend
venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
uvicorn binds IPv4 loopback (`127.0.0.1`). The frontend therefore calls the API at
`http://127.0.0.1:8000`, **not** `http://localhost:8000` — on Windows `localhost` resolves to IPv6
`::1` first, and the browser burns its full (~2 min) IPv6 connect timeout on that dead address
before falling back to IPv4. If you override the API base, keep it on `127.0.0.1`.

`/docs` (Swagger UI) lists every route. On Windows, `uvicorn --reload` can get stuck mid-reload
after rapid successive file edits (spawns its worker on the system Python instead of the venv's,
then silently stops picking up changes) — if a route seems to be serving stale code after an edit,
kill the process tree and restart plain (no `--reload`) rather than trusting the reload.

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
Vite defaults to port 5173; if that's taken it picks 5174+ automatically — if so, add that origin
to `allow_origins` in `backend/app/main.py` (CORS) or the dashboard's API calls will fail silently.

**Tests / build**
```
cd backend && venv\Scripts\python.exe -m pytest tests -q   # 113 tests: engine + quote parser
cd frontend && npm run build                                 # tsc + vite, no TS errors expected
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

## Voice setup (optional)

Both the Telegram voice-note path and the dashboard mic button use `backend/app/services/voice.py`
(plain `httpx`, no SDK) against ElevenLabs. **With `ELEVENLABS_API_KEY` blank, both stay fully
runnable** — `/api/voice/transcribe` returns a fixed field-note transcript and `/api/voice/speak`
returns 204, same stub discipline as the Telegram/SMTP fallbacks. To turn on real transcription:

```
ELEVENLABS_API_KEY=<your key>
ELEVENLABS_VOICE_ID=<a voice id from elevenlabs.io/app/voice-library>
ELEVENLABS_STT_MODEL=scribe_v1
```

## Demo script — corrected numbers

`New_PRD.md` §6 is the 4-minute script. Its Minute 2:15–3:15 narrative text says the Longi
Hi-MO7 550W + Huawei SUN2000-10KTL-M1 pairing (20 panels) resolves to "3S × 5P" at 92% confidence —
that line was the calculation spec's own 15-panel worked example copy-pasted into the 20-panel
demo scenario. The engine's actual, verified output for that exact pairing is **8S × 3P**, Vmp
332.0 V, Voc 396.8 V (well inside the 500 V MPPT window), DC:AC 1.1, a 20 A gPV fuse, and
confidence **91** — status `pass` with an `ORPHAN_PANELS` warning (4 panels short of a full third
string). Use these numbers when narrating the demo; `ARD.md` and `frontend/src/lib/fixtures.ts`
already reflect them. Full root-cause writeup: `checkpoints/PHASE_1A_ENGINE.md`.

## Test photos

Drop test images into `backend/uploads/`, then run:
```
cd backend
venv\Scripts\python.exe test_photos.py
```
This calls `analyze_photo()` directly on every file in that folder and prints the vision LLM result, bypassing Telegram.
