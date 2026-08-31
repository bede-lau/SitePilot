# Phase 1D — Frontend Application Layer (Agent D)

**Status: done + verified.** `npm run build` clean (tsc + vite, no TS errors, no unused imports).
Manually exercised every route in Chrome (light + dark) with the backend intentionally offline —
every page degrades to a skeleton or a designed empty state instead of crashing, chat streaming
error + retry confirmed end-to-end, ⌘K palette confirmed, one real robustness bug found and fixed
along the way (see §5).

---

## 1. Files built (exclusively mine, per the task's file ownership)

| Path | Purpose |
|------|---------|
| `frontend/src/components/chat/ChatPanel.tsx` | Docked/sheet/full-screen chat shell; owns text + attachment state, wires `useChatSession` + `useAttachmentUploads`, `/` focuses composer, Esc exits full-screen |
| `frontend/src/components/chat/MessageList.tsx` | User/assistant turns, auto-scroll-respects-scroll-up, tool trace, warnings, cards, error+retry |
| `frontend/src/components/chat/Composer.tsx` | Autosize textarea, ⌘↵/Ctrl+↵ send, paste-to-upload, attachment pills, disabled while streaming |
| `frontend/src/components/chat/Dropzone.tsx` | Whole-panel drag overlay (enter-depth counter so it doesn't flicker over children) |
| `frontend/src/components/chat/MicButton.tsx` | Press-and-hold record, live waveform from `AnalyserNode`, drag-away-to-cancel, permission-denied message |
| `frontend/src/components/chat/ToolTrace.tsx` | Collapsible chips from `tool`/`tool_result` events — spinner → check/cross + elapsed ms |
| `frontend/src/components/chat/StreamingText.tsx` | Capped chars/sec reveal so bursty deltas still read as a smooth stream; reduced-motion aware |
| `frontend/src/components/chat/SuggestionChips.tsx` | Seeded with the PRD §6 demo prompts |
| `frontend/src/components/chat/index.ts` | Barrel |
| `frontend/src/components/cards/QuoteCard.tsx` | Line-item table, RM/Wp hero metric, Tier-1 badges, flagged-row tooltips |
| `frontend/src/components/cards/FeasibilityCard.tsx` | Confidence + stats + string diagram + MPPT window + DC:AC range meter + tabbed check matrix |
| `frontend/src/components/cards/StringDiagram.tsx` | Animated SVG series×parallel array → inverter wiring, staggered draw-in |
| `frontend/src/components/cards/BosSpecCard.tsx` | Grouped BOS checklist, copy-as-markdown |
| `frontend/src/components/cards/FinancialCard.tsx` | Savings headline, payback **range**, 25-yr cumulative-net area chart, before/after bill |
| `frontend/src/components/cards/ConfidenceBadge.tsx` | Radial gauge + breakdown popover; hard-caps display at 94; disclaimer always adjacent, never gated |
| `frontend/src/components/cards/PoCard.tsx` | Approve & Generate PO → `/api/po/generate` → success state |
| `frontend/src/components/cards/ProjectSummaryCard.tsx` | Compact project card + "Open project" |
| `frontend/src/components/cards/VendorListCard.tsx` | Vendor match list |
| `frontend/src/components/cards/RfqStatusCard.tsx` | RFQ batch table — reads its payload defensively, see §4 |
| `frontend/src/components/cards/ComponentPickCard.tsx` | Module/inverter pick card — reads its payload defensively, see §4 |
| `frontend/src/components/cards/CardRenderer.tsx` | `card_type` → component switch |
| `frontend/src/components/cards/index.ts` | Barrel |
| `frontend/src/hooks/useChatSession.ts` | Owns message list + SSE wiring (`lib/sse.ts`) + tool-trace/warning accumulation + retry |
| `frontend/src/hooks/useAttachmentUploads.ts` | Optimistic pill → `/api/uploads` pipeline |
| `frontend/src/hooks/useVoiceRecorder.ts` | MediaRecorder + AnalyserNode wrapper for `MicButton` |
| `frontend/src/hooks/useAutoScroll.ts` | Sticky-to-bottom scroll helper |
| `frontend/src/pages/Feasibility.tsx` | New — engineering workbench |
| `frontend/src/pages/Procurement.tsx` | New — quote inbox |
| `frontend/src/pages/Components.tsx` | New — catalog browser |
| `frontend/src/pages/Dashboard.tsx` | Rewritten — Command Center |
| `frontend/src/pages/ProjectsList.tsx` | Restyled onto the design system |
| `frontend/src/pages/ProjectDetail.tsx` | Restyled + gained Design/Quotes/Financials tabs alongside the existing three |
| `frontend/src/pages/Vendors.tsx` | Restyled onto a `Table`, added BNEF tier + brands-carried columns |
| `frontend/src/pages/PurchaseOrdersList.tsx` | Restyled onto a `Table` |
| `frontend/src/components/ActivityFeed.tsx` | Restyled onto design tokens (was hardcoded Tailwind grays) — not explicitly owned by anyone, only consumed by Dashboard |
| `frontend/src/App.tsx` | Routes wired to the three new pages (was placeholder `EmptyState`s) |
| `frontend/src/components/Layout.tsx` | Docked `ChatPanel` in the reserved aside; added the <1280px floating toggle + bottom `Sheet` host |
| `checkpoints/PHASE_1D_FRONTEND_APP.md` | This file |

`components/StatCard.tsx`, `BarChart.tsx`, `ProgressBar.tsx` are now unused (superseded by
`ui`/`charts` primitives) but left in place rather than deleted — harmless, out of scope.

---

## 2. Build result

```
cd frontend && npm run build
> tsc -b && vite build
✓ 2299 modules transformed
dist/index.html                   1.49 kB
dist/assets/index-*.css          42.80 kB
dist/assets/index-*.js          521.48 kB
✓ built in ~1-3s
```

Clean — no TS errors, no unused imports (`noUnusedLocals`/`noUnusedParameters` are on in
`tsconfig.app.json`). `npx eslint .` also clean on every file this pass touched; the only
remaining eslint findings project-wide are pre-existing `react-hooks/set-state-in-effect`
notices on the standard "fetch in a `useEffect`, `setState` in `.then()`" pattern used
consistently since before this pass (Dashboard, ProjectDetail, etc. all did this originally) —
not a build blocker, and rewriting the codebase's data-fetching idiom was out of scope.

---

## 3. API endpoints called, per page

| Page | Endpoints |
|------|-----------|
| `/` Dashboard | `GET /api/overview`, `GET /analytics/overview`, `GET /events` (via `useActivityFeed`) |
| `/feasibility` | `GET /projects`, `GET /api/components` ×2, `POST /api/feasibility/run` |
| `/procurement` | `GET /api/quotes`, `POST /api/uploads`, `POST /api/quotes/parse` |
| `/components` | `GET /api/components` |
| `/projects`, `/projects/:id` | `GET /projects`, `GET /projects/:id`, `GET /inspections`, `GET /invoices`, `GET /purchase-orders`, `GET /vendors`, `GET /analytics/overview`, `GET /api/feasibility?project_id=`, `GET /api/quotes` |
| `/vendors` | `GET /vendors`, `GET /analytics/overview` |
| `/purchase-orders` | `GET /purchase-orders`, `GET /projects`, `GET /vendors` |
| Chat (all pages, docked/sheet) | `GET /api/chat/history`, `POST /api/chat/stream` (SSE), `POST /api/uploads`, `POST /api/voice/transcribe`, `POST /api/po/generate` (from `PoCard`) |

---

## 4. Deviations / underspecified contract areas

- **`rfq_status` and `component_pick` card payload shapes are not in ARD §5.3/§5.4.** Built both
  defensively: read a couple of plausible key names, fall back to an em-dash/empty state for
  anything absent, never guess a value. If the real backend shape differs, only
  `RfqStatusCard.tsx` / `ComponentPickCard.tsx` need updating.
- **`SupplierQuote` has no `project_id`.** `POST /api/quotes/parse` accepts an optional
  `project_id`, but the response type doesn't carry it back, so the Project Detail → Quotes tab
  can't actually scope quotes to the project — it shows every parsed quote workspace-wide with an
  explicit on-page note saying so, rather than silently mis-scoping.
- **No RFQ batch list endpoint.** `/procurement`'s "RFQ batch tracker" panel is an `EmptyState`
  pointing at chat rather than a fetch to a nonexistent endpoint.
- Confidence display hard-caps at 94 in `ConfidenceBadge` regardless of what the API returns
  (PRD §4.5 guardrail), and the disclaimer is always rendered adjacent to the score, never behind
  the breakdown popover.

---

## 5. Bug found + fixed during verification

`PurchaseOrdersList.tsx` had two `api.listProjects()/listVendors()` calls (used only for name
lookups, not gating any loading UI) with no `.catch()`. With the backend offline these produced
genuine unhandled promise rejections (confirmed via Chrome console — `TypeError: Failed to fetch`
logged as an uncaught exception on every mount). Fixed by adding `.catch(() => {})`; also audited
every other page's fetch calls and hardened `ProjectDetail.tsx`'s (6 calls were missing catches,
including `getProject` itself, which would have left the page stuck on its skeleton forever on a
failed fetch instead of showing an error state — added a `projectError` state + `EmptyState`).

---

## 6. Primitives extended

None needed forking. `Segmented`, `Tabs`, `Table`, `RadialGauge`, `MpptWindowBar`, `RangeMeter`,
`AreaChart`, `Sparkline` all had exactly the props needed as-is.

---

## 7. Verified in Chrome (backend intentionally offline)

- All 7 pages + docked chat render correctly in **dark** theme; Dashboard also spot-checked in
  **light** theme (theme toggle works, both look correct).
- Every page shows a designed skeleton while loading, then a designed `EmptyState` on fetch
  failure — none crash or hang.
- ⌘K/Ctrl+K command palette opens and lists every route.
- Suggestion chip click populates the composer + focuses it; send triggers the streaming UI
  ("Thinking…" status), and on the inevitable `Failed to fetch` (no backend) the assistant bubble
  shows the error with a working **Retry** button that re-sends the same turn.
- 1280px→right-rail-dock vs bottom-sheet breakpoint: confirmed via the compiled CSS containing the
  `80rem`/1280px `xl:` media query for the relevant `hidden`/`flex` utilities (the sandboxed
  browser's window could not actually be resized below its fixed 1440px viewport in this
  environment, so this is a build-artifact check rather than a live 768px screenshot — the same
  `hidden … xl:flex` pattern was already in place for the sidebar before this pass).

---

## 8. What remains

- Live verification against a running backend (quote drag-drop → parse → feasibility → PO chain,
  voice transcription, real SSE event stream) — everything above was necessarily exercised against
  an offline backend, which is what proves the degrade-gracefully requirement but can't confirm the
  happy path renders the cards correctly against real data. The fixtures in `lib/fixtures.ts` mirror
  the frozen ARD §5.3/§5.4 shapes, and all card components were written directly against those types,
  but an end-to-end run once the other agents' backend pieces land is the real test.
- A literal 768px-viewport screenshot (tooling limitation in this sandbox, see §7).
- `dist/assets/index-*.js` is 521 kB (over Vite's 500 kB warning threshold) — not addressed;
  code-splitting the chat/cards bundle behind a route-level `lazy()` would be the next step if this
  becomes a real problem, but wasn't in scope here.
