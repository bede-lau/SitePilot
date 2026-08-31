# Phase 1C — Platform Layer Verification (Agent C audit)

**Status: verified, nothing broken, nothing fixed (nothing needed fixing).** Agent C's build (models,
routes, agents/tools, voice, seed, db_upgrade) was already correct end to end. I ran a full audit —
imports, migration idempotency, seed integrity, every listed endpoint, the SSE chat protocol, the
Telegram routing path, voice stubs, and (once `app/engine/**` + `app/data/*.csv` + `app/data/bnef.py`
landed mid-run from the engine agent) the complete PRD §6 demo chain with real numbers. No code changes
were made to any Agent C file.

---

## 1. Imports & boot

```
cd backend && PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c "from app.main import app; print(len(app.routes))"
36
```
Clean both before and after `app/engine/**`/`app/data/**` landed (re-ran after). Full test suite:
```
venv/Scripts/python.exe -m pytest tests -q
113 passed in 1.04s    # (38 quote_parser + 75 engine, once engine landed — matches engine agent's own count)
```

## 2. Schema migration (`db_upgrade.py`) — idempotent, confirmed

Copied the real `fieldbot.db`, ran `run_upgrade()` twice against the copy:
```
first run ok
second run ok
```
`PRAGMA table_info` after both runs: `projects` has 21 columns (12 original + 9 ARD §3.1, all present,
zero duplicates), `vendors` has 13 columns (9 original + 4 ARD §3.2, zero duplicates). `main.py`'s
lifespan calls `Base.metadata.create_all` then `run_upgrade(conn)` — wired correctly (`app/main.py:44-46`).

## 3. Seed integrity — the evidence

Compared the **live `fieldbot.db`'s pre-existing values** (read directly, before running anything) against
`app/seed.py`'s hardcoded values, then ran `python -m app.seed` against an isolated scratch DB
(`DATABASE_URL` override — never touched the real `fieldbot.db`) and re-checked.

**Vendors — before (live db) vs. seed.py, all 6, byte-for-byte on name/email/on_time_rate/unit_price_myr:**

| Company | Live db (email, on_time, unit_price) | seed.py (same fields) | Match |
|---|---|---|---|
| YSP Solar Sdn Bhd | orahome.mail+ysp@…, 94, 320 | same | ✅ |
| Green Energy Supply | orahome.mail+greenenergy@…, 87, 300 | same | ✅ |
| SunTech Materials | orahome.mail+suntech@…, 98, 340 | same | ✅ |
| Apex Mounting Systems | orahome.mail+apex@…, 91, 280 | same | ✅ |
| Borneo PowerTech | orahome.mail+borneo@…, 89, 360 | same | ✅ |
| Voltguard Electrical | orahome.mail+voltguard@…, 96, 250 | same | ✅ |

**Projects — before vs. seed.py, all 5, name/client_name/contract_value:**

| Project | Live db | seed.py | Match |
|---|---|---|---|
| Greenfield Industrial Solar Phase 1 | Greenfield Manufacturing Sdn Bhd / 150000 | same | ✅ |
| KL Tech Park Phase 2 | KLTP Holdings Berhad / 120000 | same | ✅ |
| Johor Bahru Rooftop Array | JB Logistics Park Sdn Bhd / 210000 | same | ✅ |
| Sungai Petani Residential Cluster | SP Township Developers / 90000 | same | ✅ |
| Kuching Eco Park Solar Farm | Sarawak Green Ventures / 280000 | same | ✅ |

(Task brief said "4 projects" — the actual, correct count is **5**: 3 with fixed seeded history
[Johor Bahru, Sungai Petani, Kuching] + 2 empty live-demo projects [Greenfield, KL Tech Park], exactly as
ARD §9 describes. seed.py matches the live db's pre-existing 5 exactly.)

**New-column backfill, verified on the scratch DB after `python -m app.seed`:**
- Exactly **one** BNEF Tier-2 vendor: `Green Energy Supply` ✅ (ARD §9)
- Exactly **one** USD vendor: `Borneo PowerTech` (`quote_currency="USD"`) ✅ (ARD §9)
- Projects backfilled: Johor Bahru `monthly_consumption_kwh=4800` commercial, Sungai Petani `780`
  domestic (hybrid), Kuching `3100` commercial — matches ARD §9 exactly; Greenfield/KL Tech Park left
  `null` as specified (live-demo projects).
- Transactional counts on a fresh seed: 5 POs, 8 invoice drafts, 8 inspection reports, 21 activity
  events — all derived from the same `STATIC_*` dicts that were already in the live db's history.
- `components`: 0 rows before `app/data/*.csv` landed (graceful warning-log skip, not an error), **45
  modules + 37 inverters** after (matches CSV row counts exactly — the alias-matching header loader in
  `seed.py` worked first try against the engine agent's actual CSV headers, no changes needed).

`reset_demo.py` reviewed: clears `purchase_orders`, `rfqs`, `invoice_drafts`, `inspection_reports`,
`activity_log`, plus the ARD §9 new tables (`quote_line_items`, `feasibility_runs`, `supplier_quotes`,
`chat_messages`); resets `conversation_sessions` to idle while preserving `project_id` context; leaves
`components` untouched. Matches spec exactly.

**The real `fieldbot.db` was never written to by this audit** — all seed/migration testing ran against
scratch copies (`DATABASE_URL` env override), verified deleted afterward. One operational note for
whoever runs the live demo: **the real `fieldbot.db` currently has 5 projects/6 vendors but 0 POs/0
invoices/0 inspections and un-backfilled columns** (`state='Selangor'`/`monthly_consumption_kwh=null` on
every project) — it predates this session's `seed.py` and needs `python -m app.seed` run against it
once (fresh file, or accept duplicate projects/vendors — `seed()` doesn't delete-before-insert) before
recording. Not a code bug; nobody has re-seeded it yet.

## 4. Endpoints — every one hit live, verified response shape

Server booted against an isolated scratch DB (`uvicorn app.main:app --port 8001`), all with the real
Dashscope key live (no mocking).

| Endpoint | Result | Shape vs. ARD §5 |
|---|---|---|
| `GET /` | 200 `{"status":"ok","service":"FieldBot backend"}` | n/a |
| `GET /docs` | 200, Swagger UI renders | n/a |
| `GET /api/overview` | 200 | All 9 ARD §5.1 fields present + `co2_factor_assumption` doc field; `generation_trend`/`spend_trend` 12-entry arrays. After a real feasibility run + PO existed: `total_capacity_kwp: 11.0`, `avg_confidence: 82.0`, `co2_avoided_tonnes: 6.73`, `po_value_myr` updated — all live-computed, not stubbed. |
| `GET /api/components?kind=module&limit=3` | 200 `[]` before CSVs, real rows after (full `Component` shape, all 19 fields) | matches §3.3 exactly |
| `GET /api/bnef/check?manufacturer=LONGi` | 200 `{"tier1":false,"source":"unavailable"}` before `bnef.py` landed → `{"tier1":true,"matched_name":"LONGi Green Energy","source":"bnef_registry"}` after | matches §5.1; lazy-import guard confirmed working both sides |
| `GET /projects`, `/vendors`, `/purchase-orders` | 200, full field set incl. new ARD §3.1/§3.2 columns | not regressed |
| `GET /api/quotes` / `/api/quotes/{id}` | 200, matches §5.4 exactly incl. `line_items[]` and `summary` | ✅ |
| `POST /api/uploads` | 200 `{file_id,filename,url,kind,size}` | matches §5.1 exactly |
| `POST /api/quotes/parse` | 200, real `qwen-vl-max` parse (~13-15s), full §5.4 shape, `vendor_matched:true` via email-domain match to seeded vendor | ✅ |
| `GET/POST /api/feasibility` | 503 with clear message before engine landed (`FeasibilityError` caught → HTTPException), 200 with full `DesignReport` (§5.3, every field present) after | ✅ — see §6 below for real numbers |
| `POST /api/po/generate` | 404 for a bogus `feasibility_run_id` before engine landed; 200 with `{po,pdf_url,telegram_sent}` and a real PDF written to `uploads/pos/` after | ✅ |
| `POST /api/voice/transcribe` | 200 `{"text":"Site has minimal shading, standard metal deck roof.","language":"en"}` (`ELEVENLABS_API_KEY` empty) | clean stub, no 500 |
| `POST /api/voice/speak` | 204 No Content (no key) | clean stub, no 500 |
| `GET /api/chat/history?session_key=` | 200, full transcript incl. cards | ✅ |
| `POST /api/chat` / `POST /api/chat/stream` | see §5 | ✅ |

## 5. SSE chat stream (`POST /api/chat/stream`) — verified against ARD §5.5

Raw frames captured with curl `-N`. All 8 event types confirmed present in `orchestrator.py`
(`status:504`, `tool:558`, `tool_result:574`, `delta:525`, `card:579`, `warning:581`, `done:593`,
`error:597`) and **exercised live**, not just read in code:
- `status` → `tool` → `tool_result` → `delta`×N → `done` for a plain Q&A (`list_projects` tool call,
  real streamed answer).
- `card` (`quote_parsed`) exercised via chat with a real file attachment — full parsed quote card, then
  the assistant's follow-up text (per ARD §5.6's system-prompt rule, doesn't repeat the numbers).
- `card`×2 (`feasibility` + `confidence`) exercised via chat once the engine landed — "Run feasibility
  for Kuching Eco Park, 30 panels" → 1 tool call, 2 cards, streamed summary, `done`.
- Graceful degrade before the engine landed: asking to run feasibility got a natural-language "that
  capability's temporarily unavailable" reply instead of a crash or a stuck stream.
- Heartbeat: `: ping - <timestamp>` comment line observed mid-stream during a 13s vision-parse call
  (matches `ping=15` in `EventSourceResponse`, ARD §5.5's "every 15s").
- Termination: every stream closed on its own well before the curl timeout (e.g. 1.3s wall-clock for a
  short reply, curl exits 0) — no hung connections.

## 6. Full PRD §6 demo chain — real numbers (ran after engine + data landed)

`quote-ysp-solar-sep26.pdf` → `/api/uploads` → `/api/quotes/parse` (project 4, Sungai Petani) →
`/api/feasibility/run` (`panel_count:20, quote_id, system_type:on_grid`) → `/api/po/generate`:

- Quote parsed: vendor auto-matched to `YSP Solar Sdn Bhd` (id 1), subtotal RM 26,785.45, Longi module
  line now correctly resolves `bnef_tier1:true, tier_match_name:"LONGi Green Energy"` (was `null` before
  `app/data/bnef.py` landed — confirms the lazy-import guard resolves automatically with no code change,
  as designed).
- Feasibility: `status:"pass"`, `actual_kwp:11.0` (20×550W), confidence **82** ("Good estimate" — Manual
  count −10 applied since no matching inspection existed for this run, Site specifics not applied since
  Sungai Petani has no roof tilt/azimuth on record), inverter auto-selected Huawei SUN2000-10KTL-M1,
  BOS spec fully populated (17.5A fuse → 20A gPV, etc.), financial: RM 26,785 system cost, RM 609.79/mo
  savings, 3.7yr payback (range 3.1–4.4). All numbers came straight from `run.results` — the platform
  layer does no arithmetic, confirmed by reading `feasibility_engine.py` (no math, only DB I/O + a single
  call to `run_design`).
- **One warning surfaced, not hidden:** `ORPHAN_PANELS` — the engine's string design for this
  Huawei/Longi/20-panel combo returns `8S×3P` (24 panels needed vs. 20 available, 4 orphaned) rather than
  the PRD's narrative `3S×5P`. **This is a known, already-documented engine-layer issue** (not a platform
  bug): the engine agent's `checkpoints/PHASE_1A_ENGINE.md` explains it's a structural property of
  `design_strings` always preferring the *largest* valid series count when the inverter's MPPT window is
  wide (120–500V) — already flagged to the team lead as a product decision (change the demo's stated
  numbers, or flip the algorithm to prefer the lowest valid series count). The platform layer surfaces it
  correctly as a `warn`-level flag rather than silently hiding or crashing on it — verified working as
  intended.
- Ran a second feasibility (Johor Bahru, photo-backed panel count, site specifics + consumption on
  record) to check the confidence composition and the 94 cap: **score 91**, "Detailed specification…"
  band, composition `85 base + 3 quote + 2 site + 1 consumption = 91` (String validation not applied this
  run). Nowhere near the 94 cap; cap enforcement itself is the engine's own unit-tested responsibility
  (`test_confidence.py`, part of the 113 passing).
- PO generated: `PO-2026-006`, RM 26,785.45, status `sent` (vendor resolved), real PDF written to
  `uploads/pos/` and served back via `/static/uploads/pos/PO-2026-006.pdf` (200 OK). `/api/overview`
  immediately reflected the new run: `total_capacity_kwp:11.0`, `avg_confidence:82.0`,
  `co2_avoided_tonnes:6.73`, updated `po_value_myr` — confirms overview aggregates live off
  `feasibility_runs`/`purchase_orders`, not a cached/stubbed value.

## 7. Telegram path — not regressed

`agents/router.py::route_intent` exercised directly (not just read):
```
photo (has_media=True)                          -> "inspection"
text, idle session                                -> "orchestrator"
"yes" while awaiting_procurement_confirm          -> "confirm"
"no" while awaiting_procurement_confirm           -> "cancel"
"maybe" while awaiting_procurement_confirm        -> "confirm_clarify"
```
All correct per CLAUDE.md's routing table (router.py has 3 additional states —
`awaiting_invoice_confirm`, `awaiting_followup_choice`, `awaiting_po_request` — beyond what CLAUDE.md
documents; pre-existing functionality, not something Agent C introduced or needed to touch).

`POST /webhook/telegram` hit live against the running scratch server with a synthetic update (`chat.id:
999999001`, a fake id — deliberately *not* the real `DEMO_PHONE_NUMBER`, so as not to push a real message
to anyone's phone): routed to `orchestrator`, called `list_projects`, attempted a real `sendMessage` to
Telegram (400, invalid chat id — expected), and the failure was swallowed exactly as `CLAUDE.md` documents
(`messaging.py` logs the traceback, returns `False`, does not raise) — webhook still returned `200 {"ok":
true}`, server stayed up. Confirms the resilience contract holds under the new platform code paths too.

Voice/audio/video_note handling (`ARD §8`) reviewed in `webhook.py:_parse_update` / `telegram_webhook` —
`getFile` → `download_telegram_media` → `transcribe` → routed as body text with a `🎤 Heard: "..."` prefix;
correctly falls back to a "couldn't make it out" reply when transcription returns empty.

## 8. Voice stubs — verified live, no 500s

`ELEVENLABS_API_KEY` empty in `.env`. `POST /api/voice/transcribe` (multipart audio) → 200, fixed stub
transcript, `language:"en"`. `POST /api/voice/speak` → 204 No Content. Both match `services/voice.py`'s
documented stub discipline (same pattern as the existing Telegram/SMTP stubs).

## 9. `LLM_TEXT_MODEL` — already correct

`backend/.env` already had `LLM_TEXT_MODEL=qwen-plus` (not `qwen-turbo`) before I started. No change
needed.

## 10. What I fixed

**Nothing.** Every check in scope passed on first try, including after the concurrent engine/data
dependency landed mid-run. No Agent C file was edited.

## 11. What's still broken / needs a decision (not mine to fix — outside Agent C's ownership)

- **String-design demo numbers** (`app/engine/strings.py`, owned by the engine agent): for the PRD's
  literal demo pairing (20 panels, Longi 550W, Huawei SUN2000-10KTL-M1 with a 120–500V MPPT window),
  `design_strings` returns `8S×3P` (with 4 orphan panels, flagged as a `warn`) instead of the narrative's
  `3S×5P`. Root cause and two proposed resolutions are fully documented in
  `checkpoints/PHASE_1A_ENGINE.md` — needs a product-narrative or algorithm decision from whoever owns
  that call, not a platform fix. Confirmed the platform layer relays it correctly (as a `warn`, with the
  actual returned numbers, not silently altered) rather than compounding the issue.
- **Real `fieldbot.db` needs a fresh seed run** before the live demo/recording (see §3) — operational
  step, not a bug.

## 12. What I stubbed

Nothing new. Existing stub paths (voice with no key, BNEF/feasibility/PO before the engine dependency
landed) were already correctly guarded by Agent C's original build — I verified them, didn't add any.

## 13. Cleanup

All testing ran against isolated scratch SQLite DBs (`DATABASE_URL` env override) and a server on port
8001 — both torn down, scratch `.db` files deleted, and the two ad-hoc test-upload PDFs I created under
`backend/uploads/quotes/` removed (only the 3 official ARD §7 fixtures remain there). The real
`backend/fieldbot.db` was read-only touched (row counts/values inspected) and never written to by this
audit — confirmed identical project/vendor row counts before and after.
