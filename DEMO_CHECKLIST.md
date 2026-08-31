# SitePilot — Demo Polish Checklist

Reference: `New_PRD.md` §6 (4-minute demo script) + `ARD.md` (build contract) + `CLAUDE.md` (how the
code works today). This file previously described a WhatsApp/Twilio prototype — the product has
used **Telegram** for some time now; that section has been corrected below rather than left stale.

## 1. Photo pre-testing (manual — do this first, budget ~1hr)

- [ ] Download 8–10 candidate solar-panel site photos (Unsplash/Pexels — search "solar panel
      installation", "rooftop solar array")
- [ ] Send each to the vision LLM via `test_photos.py` (see "Test photos" in `README.md`) — this
      calls `analyze_photo()` directly, bypassing Telegram
- [ ] Pick the 3 most accurate/compelling results for the recording
- [ ] `analyze_photo()` is a real `qwen-vl-max` vision call whenever `LLM_API_KEY` is set (it is, by
      default in this repo) — photo content genuinely affects the result, unlike the old stub

## 2. Reset between attempts

Run before every dry run / recording take:
```
cd backend
export PYTHONIOENCODING=utf-8
venv/Scripts/python.exe -m app.reset_demo
```
Clears `inspection_reports`, `invoice_drafts`, `purchase_orders`, `activity_log`, `rfqs`, plus the
newer transactional tables `supplier_quotes`, `quote_line_items`, `feasibility_runs`,
`chat_messages`; resets all `conversation_sessions.state` to `idle` while preserving `context`
(so the demo phone stays bound to its project). **Does not touch** `projects`, `vendors`, or
`components` — those are seed data, not demo output.

**If `fieldbot.db` predates a code change to `app/seed.py` or `app/models/models.py`** (new
columns un-backfilled, or a schema constraint changed), `reset_demo.py` isn't enough — delete the
file and reseed fresh instead:
```
cd backend
rm fieldbot.db
venv/Scripts/python.exe -m app.seed
```
Confirms in the seed output / a quick check: 5 projects, 6 vendors (exactly 1 BNEF Tier-2, exactly
1 quoting in USD), `components` table with 45 modules + 37 inverters.

## 3. Demo project association (Telegram)

The demo Telegram chat id (`DEMO_PHONE_NUMBER` in `backend/.env` — a numeric id from
[@userinfobot](https://t.me/userinfobot), *not* a WhatsApp number) is seeded with
`context={"project_id": 1}` in `app/seed.py`, and `reset_demo.py` does not touch `context` —
confirmed via direct DB read that it survives a reset. No "which project?" prompt will appear
mid-demo for that chat id. See `README.md` → "Telegram bot setup" for registering the webhook via
ngrok.

## 4. Dry run — Telegram half (Act 1 of the PRD script, do 3x)

- [ ] `backend`: `venv/Scripts/python.exe -m app.reset_demo`
- [ ] `backend`: `venv/Scripts/python.exe -m uvicorn app.main:app --port 8000`
- [ ] `frontend`: `npm run dev`
- [ ] ngrok tunnel running, Telegram webhook URL updated to the current ngrok URL (`setWebhook`)
- [ ] Send a real rooftop photo via Telegram → confirm "Analyzing…" reply, then the full inspection
      report reply within ~15–20s
- [ ] Optionally speak a voice note ("Site has minimal shading, standard metal deck roof.") →
      confirm the reply is prefixed with `🎤 Heard: "..."` and the transcript is acted on (stub-safe
      if `ELEVENLABS_API_KEY` is blank — the transcript will be a fixed field note, not a real
      transcription, but the flow must not crash)
- [ ] Dashboard: `/` Command Center activity feed shows the new inspection event sliding in;
      `/projects/:id` → inspection + invoice draft visible
- [ ] Ask the bot something like "we're 15 panels short, need them urgently" → confirms an RFQ
      starts (simulated-quote path unless SMTP is configured — see README "Procurement: real email
      vs simulated") and a "waiting for quotes" reply, then a quote comparison after the delay
- [ ] Reply `YES` → confirm PO confirmation message on Telegram
- [ ] Dashboard: activity feed shows PO created; `/purchase-orders` shows the new PO with
      vendor/total/status "sent"
- [ ] Note any timing issues, LLM latency surprises, or UI glitches and fix before the next take

## 5. Dry run — dashboard half (Acts 2–4 of the PRD script, do 3x)

- [ ] Load `/` — Command Center shows real KPIs from `/api/overview`, not an empty state
- [ ] Go to `/procurement`, drop one of the pre-generated fixtures from `backend/uploads/quotes/`
      (or use chat: attach the file, prompt "Extract this quote, normalize the unit economics, and
      check manufacturer tier status.") → confirm a real parse (qwen-vl-max, ~13–15s), the
      `QuoteCard` renders real line items, RM/Wp, and a BNEF tier badge
- [ ] In chat, ask "Can we pair these panels with a standard 10kW Huawei string inverter?" →
      confirm `run_feasibility` fires, a `FeasibilityCard` streams in with the `StringDiagram`,
      `MpptWindowBar`, and check matrix. **Use the corrected numbers when narrating** — see
      "Demo script — corrected numbers" in `README.md` (8S × 3P / Vmp 332.0 V / Voc 396.8 V /
      confidence 91, not the PRD narrative's 3S×5P/92%). Confirm the confidence badge never shows
      above 94 and the "AI-estimated, installer-confirmed" disclaimer is visible next to it
- [ ] Ask for the payback period (the suggestion chip "What's the payback period for the
      Greenfield project?" is the exact scripted phrasing, but any natural rephrasing mentioning
      "payback"/"financial"/"savings" should also trigger `financial_analysis` — it's forced, not
      left to the model's judgment) → confirm `FinancialCard` renders with a payback **range**
      (never a single number) and the 25-year cumulative chart
- [ ] Click **Approve & Generate PO** (on the `/feasibility` page's `PoCard`, or approve via chat)
      → confirm a real PO is created, a real PDF lands in `backend/uploads/pos/`, and (if
      `TELEGRAM_BOT_TOKEN`/`DEMO_PHONE_NUMBER` are set to a real chat) it's pushed to Telegram
- [ ] Check `/feasibility` and `/components` load real data directly (not just via chat)
- [ ] Toggle light/dark theme on at least two pages — no visual breakage
- [ ] Try the dashboard mic button — stub-safe with no `ELEVENLABS_API_KEY` (no crash, just no real
      transcription)

## 6. WhatsApp/Telegram formatting check

- [ ] All RM amounts render with `RM` prefix and correct decimal formatting
- [ ] No broken/garbled characters (emoji, bullets) in any agent reply on the actual phone —
      remember `PYTHONIOENCODING=utf-8` is a *console-display* fix on Windows only; it doesn't
      affect what Telegram itself receives

## 7. Frontend polish

- [ ] Fonts load correctly at recording resolution
- [ ] No layout breaks on the screen-recording resolution
- [ ] Activity feed slide-in animation looks smooth (no jank)
- [ ] `npm run build` is clean right before recording (catches anything a last-minute edit broke)

## 8. Recording

- [ ] BEFORE segment: staged messy-PDF-in-inbox / spreadsheet clip if the script calls for one
- [ ] Full 4-minute demo recording per `New_PRD.md` §6 timing (0:00–1:00 field capture,
      1:00–2:15 quote ingestion, 2:15–3:15 feasibility, 3:15–4:00 financial + PO dispatch)
