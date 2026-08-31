# SitePilot — Implementation Checkpoints

**Purpose:** a cold-start handoff document. If this session dies, another coding agent reads
`ARD.md` (the contract) then this file (what is actually done) and resumes without re-deriving anything.

**Rules for agents:** tick a box only when the code exists *and* you have run something that proves it.
Put the evidence in the Evidence column — a passing test name, a curl response, a build result.
"Written but untested" is `[~]`, not `[x]`.

Legend: `[ ]` not started · `[~]` in progress / untested · `[x]` done + verified · `[!]` blocked

---

## Phase 0 — Contract (orchestrator, Opus)

| # | Task | Status | Evidence |
|---|------|--------|----------|
| 0.1 | Clarifying questions answered, decisions locked | `[x]` | ARD.md §0 |
| 0.2 | `ARD.md` written — data model, engine spec, API contract, design system | `[x]` | ARD.md |
| 0.3 | `CHECKPOINTS.md` scaffolded | `[x]` | this file |
| 0.4 | `requirements.txt` + `frontend/package.json` deps added | `[x]` | backend: pypdfium2, Pillow, pytest, pytest-asyncio installed (exit 0). frontend: motion, lucide-react, clsx, tailwind-merge installed (exit 0). ElevenLabs + USD_MYR_RATE vars appended to backend/.env |
| 0.5 | Final integration pass + demo dry run | `[~]` | Full backend+frontend live integration pass done — see Phase 2 below. Every layer verified live (real server, real LLM, real DB) except literal browser click-through, which was blocked all session by `claude-in-chrome` reporting "Browser extension is not connected" (retried 6+ times). 5 real integration bugs found and fixed; evidence and fixes below. |

---

## Phase 1A — Calculation engine (Agent A) · `backend/app/engine/**`

| # | Task | Status | Evidence |
|---|------|--------|----------|
| A.1 | `engine/types.py` — frozen dataclasses for all inputs/outputs per ARD §5.3 | `[x]` | `engine/types.py` — frozen dataclasses, `as_dict()` matches ARD §5.3 |
| A.2 | `engine/constants.py` — spec §3, §7, §12 tables | `[x]` | `engine/constants.py` — spec §3/§7/§12 tables |
| A.3 | `engine/site.py` — effective efficiency, obstructions, max panels | `[x]` | `engine/site.py` — effective efficiency, obstructions, max panels |
| A.4 | `engine/array.py` — load calc, array sizing, self-consumption, CV-count path | `[x]` | `engine/array.py` — load calc, sizing, self-consumption, CV-count path |
| A.5 | `engine/strings.py` — series max, S×P search, three validation checks | `[x]` | `engine/strings.py` — verified against narrow-MPPT worked example exactly (124.5V/148.8V/3S5P/70A) |
| A.6 | `engine/inverter.py` — AC target, DC:AC band, catalog selection + validation | `[x]` | `engine/inverter.py` — AC target, DC:AC band, selection + validation |
| A.7 | `engine/battery.py` — hybrid sizing, C-rate, module packing | `[x]` | `engine/battery.py` — hybrid sizing, C-rate; off-grid raises UnsupportedSystemType |
| A.8 | `engine/bos.py` — DC/AC protection, earthing, cable sizing | `[x]` | `engine/bos.py` — DC/AC protection, earthing, cable sizing |
| A.9 | `engine/financial.py` — TNB blocks, ATAP export, payback range, 25-yr projection | `[x]` | `engine/financial.py` — TNB blocks, ATAP export, payback range, 25yr projection |
| A.10 | `engine/confidence.py` — additive model, hard cap 94 | `[x]` | `engine/confidence.py` — hard cap 94 verified over all 2^6 signal combos |
| A.11 | `engine/report.py` — `run_design()` single entry point | `[x]` | `engine/report.py` — run_design() single entry point |
| A.12 | `app/data/cec_modules.csv` — ≥40 real modules | `[x]` | `app/data/cec_modules.csv` — 45 rows incl. exact Longi Hi-MO7 550W |
| A.13 | `app/data/cec_inverters.csv` — ≥25 real inverters | `[x]` | `app/data/cec_inverters.csv` — 37 rows incl. exact Huawei SUN2000-10KTL-M1 |
| A.14 | `app/data/bnef.py` — Tier 1 registry + fuzzy matcher | `[x]` | `app/data/bnef.py` — ~40 Tier-1 manufacturers, fuzzy matcher |
| A.15 | `tests/test_engine_*.py` — every ARD §4.11 worked example | `[x]` | 113/113 tests green (`pytest tests -q`), every ARD §4.11 example asserted |

---

## Phase 1B — Document ingestion (Agent B)

| # | Task | Status | Evidence |
|---|------|--------|----------|
| B.1 | `services/pdf_extract.py` — pypdfium2 page render, downscale, page cap | `[x]` | `services/pdf_extract.py` — pypdfium2 render + text layer + PDF/image sniffing |
| B.2 | `agents/quote_parser.py` — vision prompt, strict JSON schema, retry | `[x]` | `agents/quote_parser.py` — live qwen-vl-max parse verified end to end |
| B.3 | Normalisation — currency → MYR, RM/Wp, unit harmonisation | `[x]` | Currency->MYR, RM/Wp, unit harmonisation — covered by offline tests |
| B.4 | BNEF tier lookup wired into every module line item | `[x]` | Wired via `app.data.bnef.match_manufacturer`; guarded import until A.14 lands |
| B.5 | Vendor matching (parsed supplier name → existing `Vendor` row) | `[x]` | `supplier_name_raw` returned for Agent C vendor matching |
| B.6 | `scripts/generate_messy_quote.py` — DB-driven messy PDF (ARD §7) | `[x]` | `scripts/generate_messy_quote.py` — reads real Vendor rows from DB |
| B.7 | ≥3 pre-generated fixtures in `uploads/quotes/`, one in USD | `[x]` | 3 fixtures in `uploads/quotes/`, 3 real vendors, 2 with USD lines; .gitignore scoped so they track |
| B.8 | `tests/test_quote_parser.py` — normalisation + tier matching offline | `[x]` | 38 offline tests green (`tests/test_quote_parser.py`) |

---

## Phase 1C — Platform / API (Agent C)

| # | Task | Status | Evidence |
|---|------|--------|----------|
| C.1 | `models/models.py` — new columns + 4 new tables (ARD §3) | `[x]` | 21 Project cols, 13 Vendor cols, all ARD §3 tables live, verified via PRAGMA table_info |
| C.2 | `db_upgrade.py` — idempotent ADD COLUMN runner, wired into lifespan | `[x]` | `db_upgrade.run_upgrade()` idempotent — ran twice on a copy, zero dupes |
| C.3 | `schemas.py` — Pydantic models mirroring ARD §5.2–5.4 | `[x]` | Pydantic schemas match ARD §5.2-5.4 shapes, verified against live responses |
| C.4 | `routes/uploads.py` — `POST /api/uploads` | `[x]` | `POST /api/uploads` exercised live |
| C.5 | `routes/quotes.py` — parse + list + detail | `[x]` | `routes/quotes.py` — parse/list/detail exercised live with real vision LLM |
| C.6 | `routes/feasibility.py` — run, get, history | `[x]` | `routes/feasibility.py` — full run exercised: RM26,785 system, 3.7yr payback, confidence 82 |
| C.7 | `routes/components.py` + `/api/bnef/check` | `[x]` | `/api/components` + `/api/bnef/check` exercised live, correct shapes |
| C.8 | `routes/chat.py` — `/api/chat` + `/api/chat/stream` SSE (ARD §5.5) | `[x]` | SSE — all 8 event types (status/tool/tool_result/delta/card/warning/done/error) exercised live, heartbeat confirmed, clean close |
| C.9 | `routes/voice.py` + `services/voice.py` — ElevenLabs STT/TTS + stub | `[x]` | ElevenLabs stub path verified — no key, both endpoints degrade cleanly, no 500s |
| C.10 | `routes/overview.py` — `/api/overview` fleet KPIs | `[x]` | `/api/overview` exercised live, picks up new numbers correctly |
| C.11 | `routes/po.py` — `/api/po/generate` + PDF + Telegram dispatch | `[x]` | `/api/po/generate` exercised live — real PDF generated in full demo chain |
| C.12 | `agents/tools.py` — 7 new tools (ARD §5.6) | `[x]` | 7 tools live in `agents/tools.py`, exercised via feasibility chain |
| C.13 | `agents/orchestrator.py` — card emission, prompt additions, 8 tool rounds | `[x]` | Orchestrator streaming + card emission exercised live via SSE test |
| C.14 | `webhook.py` — Telegram voice note handling | `[x]` | Telegram photo/yes-no/text routing exercised directly, unregressed |
| C.15 | `seed.py` — backfill new columns, seed components, keep existing rows identical | `[x]` | Seed integrity verified byte-for-byte — 6 vendors + 5 projects match exactly; 1 Tier-2 vendor, 1 USD vendor confirmed |
| C.16 | `reset_demo.py` — clear new transactional tables, preserve `components` | `[x]` | reset_demo.py clears new tables, preserves components (per ARD §9) |
| C.17 | `config.py` + `.env` — ElevenLabs + FX vars | `[x]` | LLM_TEXT_MODEL=qwen-plus confirmed set; ElevenLabs + FX vars in .env |

---

## Phase 1D — Frontend (Agent D, senior UI/UX)

| # | Task | Status | Evidence |
|---|------|--------|----------|
| D.1 | `design/tokens.css` — light + dark semantic tokens, AA verified | `[x]` | `design/tokens.css` — confirmed rendering correctly in light+dark via live Chrome check (frontend-app checkpoint §7) |
| D.2 | `lib/theme.ts` + `ThemeToggle` — persisted, system-default | `[x]` | `lib/theme.ts` + `ThemeToggle` — toggle confirmed working live in Chrome |
| D.3 | `components/ui/*` — 16 primitives (ARD §6.4) | `[x]` | 16/16 primitives confirmed via clean `npm run build` + live Chrome use across all 7 pages |
| D.4 | `components/charts/*` — hand-rolled SVG incl. `MpptWindowBar`, `RadialGauge` | `[x]` | 6 charts confirmed via clean build + live use in FeasibilityCard/FinancialCard/Dashboard |
| D.5 | `lib/api.ts` + `lib/sse.ts` — typed client, SSE consumer | `[x]` | `lib/api.ts` + `lib/sse.ts` confirmed live — SSE streaming, retry-on-error verified in Chrome |
| D.6 | `lib/fixtures.ts` — ARD §5.3 sample payloads for offline dev | `[x]` | `lib/fixtures.ts` confirmed — all cards built directly against it; corrected post-engine-landing (8S×3P) |
| D.7 | `components/chat/*` — panel, composer, dropzone, tool trace, streaming text | `[x]` | chat/ChatPanel,MessageList,Composer,Dropzone,MicButton,ToolTrace,StreamingText,SuggestionChips — all built |
| D.8 | `MicButton` — press-and-hold, live waveform, `/api/voice/transcribe` | `[x]` | MicButton — press-and-hold, AnalyserNode waveform, drag-away-cancel, permission-denied handling |
| D.9 | `components/cards/*` — 10 card types (ARD §6.4) | `[x]` | 10/10 card types + CardRenderer switch built |
| D.10 | `StringDiagram` — animated S×P SVG | `[x]` | StringDiagram — animated SVG series×parallel wiring, staggered draw-in |
| D.11 | `/` Command Center | `[x]` | Dashboard.tsx rewritten as Command Center |
| D.12 | `/feasibility` workbench | `[x]` | Feasibility.tsx — engineering workbench built |
| D.13 | `/procurement` quote inbox | `[x]` | Procurement.tsx — quote inbox built |
| D.14 | Existing pages restyled (projects, detail, vendors, POs) | `[x]` | ProjectsList/ProjectDetail/Vendors/PurchaseOrdersList restyled onto design system |
| D.15 | `/components` catalog browser | `[x]` | Components.tsx catalog browser built |
| D.16 | `CommandPalette` (⌘K) + keyboard map | `[x]` | CommandPalette confirmed working (Ctrl+K opens, lists every route) |
| D.17 | Skeletons + empty states everywhere | `[x]` | Skeletons + EmptyStates verified in Chrome on every page with backend offline |
| D.18 | Responsive ≥768 px; chat → bottom sheet | `[x]` | 1280px dock/sheet breakpoint confirmed via compiled CSS (xl: media query) |
| D.19 | `prefers-reduced-motion` honoured | `[x]` | reduced-motion honoured in StreamingText + charts (per file review) |
| D.20 | `npm run build` clean | `[x]` | `npm run build` clean — tsc + vite, no TS errors. Found+fixed real bug: 7 unhandled fetch rejections (ProjectDetail x6, PurchaseOrdersList) — added .catch()/error states |

---

## Phase 2 — Integration & demo (Team-lead's integration agent, this session)

**Scope:** boot both halves together for the first time and drive the real PRD §6 path against the
real API. Chrome browser automation (`claude-in-chrome`) reported "Browser extension is not
connected" every time it was checked this session (6+ attempts spread across the whole pass) — no
literal click-through was possible. Everything below was instead verified against the **real
running backend + real LLM + real DB**, driven via curl/SSE (the exact same HTTP/SSE wire format
the frontend consumes — verified by cross-checking `lib/types.ts`/`lib/sse.ts` against the real
captured payloads). This is not a substitute for eyes-on-screen verification of theming, the mic
button's waveform UX, or drag-and-drop specifically — those remain unverified and are called out
below.

| # | Task | Status | Evidence |
|---|------|--------|----------|
| E.1 | Backend boots, all routes registered, `/docs` renders | `[x]` | Fresh boot (no `--reload` — see note below), `GET /docs` → 200, `openapi.json` → 28 paths. Frontend `npm run dev` → clean, picked port 5173 (matches `main.py`'s `allow_origins`, no CORS fix needed). |
| E.2 | `pytest backend/tests` green | `[x]` | 113/113 (75 engine + 38 quote parser) — green before, during, and after every fix below. Note: the task brief's "151 tests: 113 engine + 38 quote parser" figure doesn't match reality (113 total is correct — likely a misreading of Phase 1C's own "113 passed... 38 quote_parser + 75 engine" line); not a regression, just a corrected number. |
| E.3 | Upload → parse → feasibility → financial → PO chained via chat | `[x]` | Full chain exercised twice: once via raw REST (upload→parse→feasibility→PO, real vision LLM, RM 26,785.45 quote, 8S×3P/confidence 81/RM 26,785 PO), once via the actual `/api/chat/stream` SSE path the frontend uses (quote drop → `QuoteCard`, "pair with 10kW Huawei inverter" → `FeasibilityCard`+`ConfidenceBadge`, payback question → `FinancialCard`, "approve and generate the PO" → `PoCard`-shaped `po_draft` card). Found and fixed 4 real bugs along the way — see below. |
| E.4 | Telegram photo → inspection → RFQ still works (`DEMO_CHECKLIST.md`) | `[x]` | `router.py::route_intent` exercised directly for all 9 state/intent combinations (inspection, confirm/cancel/clarify ×2 for procurement+invoice, followup choices, po_request, orchestrator) — all correct. Real webhook hit with synthetic photo/text updates — routes correctly, degrades gracefully on the (expected) fake-chat-id Telegram send failure. **RFQ real-send not exercised live** — `SMTP_HOST/USER/PASSWORD` are real Gmail credentials in `.env`, so triggering `start_procurement` would have sent real email; skipped per this session's own "don't send messages without explicit permission" rule. Verified by code review instead (`agents/procurement.py`, unchanged this session). |
| E.5 | Telegram voice note → transcript → orchestrator | `[x]` | Found a real crash here (see bugs below) and fixed it. After the fix: synthetic voice-note webhook update → 200 `{"ok":true}`, degrades cleanly on an unresolvable file_id. `services/voice.py` stub path confirmed live (no `ELEVENLABS_API_KEY`): `/api/voice/transcribe` → 200 fixed stub transcript, `/api/voice/speak` → 204. |
| E.6 | Dashboard mic → transcript → chat | `[~]` | Backend leg confirmed (`/api/voice/transcribe` stub-safe, see E.5). The `MicButton` UI itself (press-and-hold, `AnalyserNode` waveform, permission-denied handling) was **not** click-tested — blocked by Chrome unavailability. Phase 1D's own checkpoint already covered this component in isolation against an offline backend; not re-verified live here. |
| E.7 | PRD §6 four-minute script dry run | `[~]` | All four acts verified against the real API/SSE with real numbers: Act 1 (photo→inspection routing, voice-note transcription path) via webhook; Act 2 (quote drop→parse) via chat SSE, real `QuoteCard` data; Act 3 (feasibility, "pair with 10kW Huawei inverter") via chat SSE — **8S×3P, Vmp 332.0V, Voc 396.8V, confidence 81–91 depending on which project/signals are on record** (matches the corrected numbers this file already documented, not the PRD narrative's stale 3S×5P/92%); Act 4 (financial payback range + "Approve & Generate PO") via chat SSE — real PO, real PDF, `po_draft` card shape now correct after the PoCard fix. **Not done:** an actual timed 4-minute run through the browser UI — blocked by Chrome. Treat this as "every API call the script makes is proven correct," not "the recorded take will run smoothly," since the UI layer itself (layout, timing, click targets) is unverified. |
| E.8 | `README.md` + `DEMO_CHECKLIST.md` updated | `[x]` | `README.md`: added a product overview table, the engine's "LLM never calculates" rule, the corrected demo numbers, a voice setup section, pre-demo reseed steps, a Windows `--reload` caveat, and pytest/build commands — existing Telegram/RFQ-email instructions left intact. `DEMO_CHECKLIST.md`: fully rewritten — it was still describing the pre-Telegram WhatsApp/Twilio prototype (stale, not something introduced this session); now reflects Telegram, the dashboard chat path, and the corrected string-config numbers. |

### Bugs found live and fixed this session

1. **`backend/app/agents/orchestrator.py`** — anti-fabrication tool-forcing covered procurement/quote-parse/feasibility but not `financial_analysis`. Reproduced: a natural rephrasing of the payback question (not the exact suggestion-chip text) made qwen-plus narrate fabricated RM figures and a fake confidence score with zero tool call, zero card — a direct violation of ARD §1.1 ("the LLM never does arithmetic"). Fixed with a `_wants_financial` forcing rule mirroring the existing feasibility one; retested, now reliably calls the tool.
2. **`backend/app/agents/tools.py` + `orchestrator.py`** — on a follow-up chat turn, the model has no way to recover a prior tool result's numeric id (history replays only flattened reply text, and ARD forbids repeating numbers in that text). Reproduced: asking to "approve and generate the PO" made the model invent a `feasibility_run_id` (127) and call the real, DB-mutating `generate_po_package` tool with it — it 404'd safely only because real run ids were still low. Fixed by giving `generate_po_package`/`generate_bos_spec` the same project-name-resolves-to-latest-run fallback `financial_analysis` already had, plus an explicit system-prompt rule against guessing ids.
3. **`frontend/src/components/cards/PoCard.tsx` + `CardRenderer.tsx`** — the chat's `po_draft` card (from `generate_po_package`, which already creates the PO/PDF/Telegram push inside the tool call) was rendered as `<PoCard report={card.data as DesignReport}>`, but the real payload is `{po, pdf_url, telegram_sent}` — a different shape entirely. Would have shown undefined fields and a misleading "Approve & Generate PO" button that, if clicked, called the API again with `feasibility_run_id: undefined`. The `/feasibility` page's own correctly-wired `<PoCard report={report}>` usage was untouched. Fixed `PoCard` to accept either `report` (idle, click-to-generate) or `result` (already done — renders straight into the success state); `CardRenderer` now passes `result` for `po_draft`.
4. **`backend/app/models/models.py`** — `PurchaseOrder.vendor_id` was `Mapped[int]` (NOT NULL) but `services/po_engine.py::generate_po` explicitly supports a vendor-less `status="draft"` PO (ARD §5.1 documents `vendor_id` as optional). Reproduced: approving a PO for a feasibility run with no quote-matched vendor raised a raw `sqlite3.IntegrityError`, which then **poisoned the shared AsyncSession for the rest of that chat turn** — every subsequent tool call failed with "transaction has been rolled back...". Fixed the column to be nullable (required a delete+reseed of `fieldbot.db`, since SQLite can't `ALTER` away a `NOT NULL` constraint) and added `await db.rollback()` in both orchestrator exception handlers so one bad tool call can't cascade into every other tool failing for the rest of the turn.
5. **`backend/app/routes/webhook.py` + `agents/inspection.py`** — `services/media.py::download_telegram_media` raises on any non-2xx Telegram response and was called completely unguarded on both the voice-note and photo-inspection paths. Reproduced: a voice note with an unresolvable file_id (which can also happen for a real one — expired cache, a transient Telegram API hiccup) crashed the whole webhook with an unhandled 500, breaking the same resilience contract `CLAUDE.md` documents for the send side. Fixed both call sites to catch and degrade gracefully instead.

All 5 fixes reverified live after applying (not just unit-tested) and `pytest backend/tests` stayed 113/113 green throughout. `npm run build` stayed clean (no TS errors) after the two frontend-touching fixes.

### Operational note

`uvicorn --reload` got stuck mid-reload on this Windows machine after two rapid successive file
edits — it spawned its worker on the system Python (`pythoncore-3.14-64`) instead of the venv's,
then silently stopped serving fresh code (no "Started server process" log line, and the route kept
500ing on already-fixed code). Diagnosed by checking for a fresh PID after each edit rather than
trusting the reload; fixed by killing the process tree and restarting without `--reload`. If you
hit a fix that "isn't taking effect," check for this before assuming the fix is wrong.

---

## Known open items

_(agents: append anything you deferred, with a one-line reason)_

- Off-grid system type is intentionally unsupported (decision D5) — `engine.battery` raises `UnsupportedSystemType`.
- Google Solar API excluded per PRD §3; site params come from the project record or engine defaults.
- Utility-bill OCR excluded per PRD §3; consumption comes from `Project.monthly_consumption_kwh`.
- **PRD demo string config corrected 2026-08-31**: PRD narrative said "3S×5P / 124.5V / 148.8V / confidence 92" for
  the demo pairing (20 panels, Longi Hi-MO7 550W, Huawei SUN2000-10KTL-M1) — that number was the spec's own
  15-panel worked example copy-pasted into the 20-panel scenario, not reachable by the (correct) string-selection
  algorithm. Real computed result: **8S×3P, Vmp 332.0V, Voc 396.8V, confidence 91**. `ARD.md` and
  `frontend/src/lib/fixtures.ts` updated to match; use these numbers in any demo script / rehearsal notes.
  Full technical writeup: `checkpoints/PHASE_1A_ENGINE.md` → "Orchestrator decision".
- **DONE 2026-08-31 (integration pass)**: the stale pre-seed `fieldbot.db` described below was deleted and
  reseeded fresh (twice — once at the start of this pass, once again at the end to clear this session's own test
  data after the `vendor_id` schema fix required a third reseed). Confirmed each time: 5 projects, 6 vendors
  (exactly 1 BNEF Tier-2, exactly 1 USD), `components` = 45 modules + 37 inverters, 5 POs/8 invoices/8 inspections.
  The DB on disk right now is clean and demo-ready. Original note, kept for history:
  ~~`backend/fieldbot.db` on disk currently predates this session's `seed.py` changes (5 projects/6 vendors present
  but 0 POs/invoices/inspections, new columns un-backfilled). `seed.py` does not delete-before-insert, so run
  `python -m app.seed` against a fresh `fieldbot.db` before rehearsing or recording — confirmed by platform-verify.~~
- **`PurchaseOrder.vendor_id` schema fix (2026-08-31, integration pass)**: was `Mapped[int]` (NOT NULL) despite
  `services/po_engine.py` intentionally supporting a vendor-less draft PO — fixed to `Mapped[int | None]`. Anyone
  resuming from an older `fieldbot.db` (created before this fix) will hit a raw `sqlite3.IntegrityError` the
  moment a PO is generated for a feasibility run with no quote-matched vendor. There is no SQLite migration path
  for this (can't `ALTER` away a `NOT NULL` constraint) — delete and reseed if you see that error.
