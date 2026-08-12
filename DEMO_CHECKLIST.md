# FieldBot — Stage 6 Demo Polish Checklist

Reference: `plan.txt` Section 10 Stage 6 + Section 11 (Demo Script).

## 1. Photo pre-testing (manual — do this first, budget ~1hr)
- [ ] Download 8–10 candidate solar-panel site photos (Unsplash/Pexels — search "solar panel installation", "rooftop solar array")
- [ ] Send each to the vision LLM (or current stub) with the inspection prompt
- [ ] Pick the 3 most accurate/compelling results
- [ ] Save as `backend/uploads/site_photo_1.jpg`, `site_photo_2.jpg`, `site_photo_3.jpg`
- Note: `analyze_photo()` in `app/services/llm_client.py` is currently a deterministic stub (no real LLM key set). If still stubbed at recording time, this step is cosmetic only — the stub's output won't vary by photo content. Wire a real vision key first if photo-accuracy matters for the recording.

## 2. Reset between attempts
Run before every dry run / recording take:
```
cd backend
venv/Scripts/python.exe -m app.reset_demo
```
Verified: clears `inspection_reports`, `invoice_drafts`, `purchase_orders`, `activity_log`; resets all `conversation_sessions.state` to `idle`. Projects, vendors, and session `context` (incl. demo phone's `project_id: 1`) are preserved.

## 3. Demo project association (verified)
Demo phone (`whatsapp:+60123456789`, from `.env` `DEMO_PHONE_NUMBER`) is seeded with `context={"project_id": 1}` in `app/seed.py`, and `reset_demo.py` does not touch `context` — confirmed via direct DB read that it survives a reset. No "which project?" prompt will appear mid-demo.

## 4. Dry run (do 3x, full Section 11 script, start to finish)
- [ ] `backend`: `venv/Scripts/python.exe -m app.reset_demo`
- [ ] `backend`: `venv/Scripts/python.exe -m uvicorn app.main:app --port 8000`
- [ ] `frontend`: `npm run dev` (port 5173)
- [ ] ngrok tunnel running, Twilio sandbox webhook URL updated to current ngrok URL
- [ ] Act 1: send 3 site photos via WhatsApp → confirm "Analyzing…" reply, then full inspection report reply within the expected ~15–20s
- [ ] Dashboard: activity feed shows new inspection event sliding in; Project Detail → inspection + invoice draft visible
- [ ] Act 2: send "We're 15 panels short for the Penang site. Need them urgently." → confirm RFQ + "waiting for quotes" reply, then quote comparison after the 8s delay
- [ ] Reply `YES` → confirm PO confirmation message
- [ ] Dashboard: activity feed shows PO created; Purchase Orders page shows new PO with vendor/total/status "sent"
- [ ] Note any timing issues, LLM latency surprises, or UI glitches and fix before next take

## 5. WhatsApp formatting check
- [ ] All RM amounts render with `RM` prefix and correct decimal formatting
- [ ] No broken/garbled characters (emoji, bullets) in any agent reply on the actual phone

## 6. Frontend polish
- [ ] Fonts load correctly at recording resolution
- [ ] No layout breaks on the screen-recording resolution
- [ ] Activity feed slide-in animation looks smooth (no jank)

## 7. Recording
- [ ] BEFORE segment: staged WhatsApp group screenshots + spreadsheet clip (manual, see Section 11 script for exact lines)
- [ ] Full Act 1 + Act 2 demo recording per Section 11 timing
