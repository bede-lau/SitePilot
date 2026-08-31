# SitePilot — Architecture & Requirements Document (ARD)

**Version:** 1.0 · 2026-08-31
**Supersedes:** nothing. **Complements:** `CLAUDE.md` (current system), `New_PRD.md` (what to build),
`Solar_AI_Calculation_Engine_Spec.docx` (the formulas). Where this ARD and the spec disagree, **this ARD wins** —
it encodes the PRD's IMPLEMENT/EXCLUDE scoping decisions.

**Progress tracking:** `CHECKPOINTS.md`. Every agent updates it on completion.

---

## 0. Decisions locked with the product owner

| # | Decision | Choice |
|---|----------|--------|
| D1 | Voice provider | **ElevenLabs** (key supplied by owner in `backend/.env`). Stub fallback when key absent. |
| D2 | Quote PDF parsing | **Render pages → `qwen-vl-max` vision** (via `pypdfium2`). Reuses the existing Dashscope key. |
| D3 | Consumption data | **New `Project` columns + synthetic seed values**, chat-overridable. Existing DB rows stay source of truth. |
| D4 | Component parameters | **Vendored CSV subset of the NREL/CEC library**, loaded into a `components` DB table at seed. No `pvlib`. |
| D5 | System types | **On-grid + Hybrid.** Off-grid explicitly out of scope (raises `UnsupportedSystemType`). |
| D6 | Theming | **Full light + dark token system with a header toggle.** Both palettes must be first-class. |
| D7 | Voice surfaces | **Dashboard chat mic** *and* **Telegram voice notes**. (Narrated summary is a stretch goal.) |
| D8 | Runway | One long session. Checkpoint aggressively so another agent can resume cold. |

---

## 1. System context

```
┌──────────────┐   photos / voice notes    ┌──────────────────────────────────────┐
│ Telegram     │ ────────────────────────► │  FastAPI backend (backend/app)        │
│ (field eng.) │ ◄──────────────────────── │                                       │
└──────────────┘   POs, RFQ updates        │  routes/  ── HTTP + SSE               │
                                            │  agents/  ── LLM tool-calling         │
┌──────────────┐   chat, PDF drop, mic     │  engine/  ── DETERMINISTIC math        │
│ React dash   │ ◄───── SSE stream ──────► │  services/── LLM, email, voice, pdf    │
│ (PM / judge) │                            │  models/  ── SQLAlchemy async         │
└──────────────┘                            └───────────────┬──────────────────────┘
                                                            │
                      ┌─────────────────────────────────────┼──────────────────────┐
                      │ Dashscope (qwen-turbo / qwen-vl-max)│ ElevenLabs (STT/TTS) │
                      │ SMTP+IMAP (RFQ loop)                │ SQLite (aiosqlite)   │
                      └─────────────────────────────────────┴──────────────────────┘
```

### 1.1 The one architectural rule

> **The LLM never does arithmetic.**

Every number a judge sees — string counts, voltages, fuse ratings, RM savings, payback years, confidence
percentages — comes out of `backend/app/engine/`, which is **pure Python: no I/O, no DB, no network, no LLM**.
The LLM's only jobs are (a) reading messy documents into structured JSON and (b) deciding which deterministic
function to call. This is the PRD's Technical Feasibility criterion (25% of judging) and it is non-negotiable.

Consequence: `engine/` is 100% unit-testable and every worked example in the spec becomes a test case.

---

## 2. Module ownership map (prevents agents colliding)

| Owner | Paths | Must not touch |
|-------|-------|----------------|
| **Agent A — Engine** | `backend/app/engine/**`, `backend/app/data/*.csv`, `backend/app/data/bnef.py`, `backend/tests/test_engine_*.py` | anything else |
| **Agent B — Ingestion** | `backend/app/services/pdf_extract.py`, `backend/app/agents/quote_parser.py`, `backend/scripts/generate_messy_quote.py`, `backend/tests/test_quote_parser.py` | `engine/`, `routes/`, frontend |
| **Agent C — Platform** | `backend/app/models/models.py`, `backend/app/schemas.py`, `backend/app/routes/**`, `backend/app/agents/{tools,orchestrator,router}.py`, `backend/app/services/{voice,chat_stream}.py`, `backend/app/seed.py`, `backend/app/main.py`, `backend/app/config.py`, `backend/app/routes/webhook.py` | `engine/`, `quote_parser.py`, frontend |
| **Agent D — Frontend** | `frontend/**` | all backend |
| **Orchestrator (Opus)** | `ARD.md`, `CHECKPOINTS.md`, `requirements.txt`, `frontend/package.json`, integration fixes | — |

`requirements.txt` and `package.json` are written **once, up front, by the orchestrator**. Agents must not edit them;
if a dependency is missing, report it in the checkpoint instead of adding it.

---

## 3. Data model changes

All additive. **No existing column is dropped or renamed. Existing seeded vendors/projects/POs/invoices remain the
source of truth.** SQLite has no migration tooling here — `Base.metadata.create_all` handles new tables, and new
columns on existing tables are applied by `app/db_upgrade.py` (Agent C: a tiny idempotent `ALTER TABLE ... ADD COLUMN`
runner invoked from the lifespan, guarded by a `PRAGMA table_info` check).

### 3.1 `Project` — new columns

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `state` | str | `"Selangor"` | PSH lookup key (spec 3.2) |
| `system_type` | str | `"on_grid"` | `on_grid` \| `hybrid` |
| `monthly_consumption_kwh` | float\|null | null | Financial engine load input (D3) |
| `tariff_category` | str | `"domestic"` | `domestic` \| `commercial` |
| `roof_area_m2` | float\|null | null | Site assessment; null ⇒ derive from `total_panels` |
| `roof_tilt_deg` | float\|null | null | Tilt factor; null ⇒ 15° default |
| `roof_azimuth_deg` | float\|null | null | Azimuth factor; null ⇒ 0° default |
| `shading_factor` | float\|null | null | null ⇒ 0.95 default |
| `obstructions` | JSON | `[]` | `[{"kind":"water_tank","count":1}, ...]` |

### 3.2 `Vendor` — new columns

| Column | Type | Purpose |
|--------|------|---------|
| `bnef_tier` | int\|null | 1 or 2; drives the warning badge |
| `brands_carried` | JSON | `["Longi","Huawei"]` — used by the messy-quote generator |
| `country` | str | default `"Malaysia"` |
| `quote_currency` | str | default `"MYR"` — one seeded vendor uses `"USD"` to exercise conversion |

### 3.3 New tables

**`components`** — seeded from the vendored CEC CSVs (D4).
```
id, kind('module'|'inverter'), manufacturer, model, tier(int|null),
# module fields
rated_wp, vmp, voc, imp, isc, temp_coeff_voc_pct_per_c, efficiency_pct, cell_tech, area_m2,
# inverter fields
ac_rating_kw, max_dc_input_kw, mppt_min_v, mppt_max_v, max_dc_voltage_v,
max_input_current_per_mppt_a, mppt_count, phase, euro_efficiency_pct, has_anti_islanding,
# shared
datasheet_url, source('CEC'|'manufacturer'|'parsed_quote'), created_at
```

**`supplier_quotes`** — one parsed PDF.
```
id, project_id(null), vendor_id(null), supplier_name_raw, source_filename, source_url,
currency, fx_rate_to_myr, page_count, parse_status('parsed'|'partial'|'failed'),
parse_notes, raw_text, raw_llm_json(JSON), subtotal_myr, created_at
```

**`quote_line_items`**
```
id, quote_id, line_no, category('module'|'inverter'|'battery'|'bos'|'service'|'unknown'),
manufacturer, model, description, quantity, unit, unit_price, currency,
unit_price_myr, line_total_myr, rated_wp, price_per_wp_myr,
warranty_years, lead_time_days, bnef_tier1(bool|null), tier_match_name, flags(JSON)
```

**`feasibility_runs`**
```
id, project_id, quote_id(null), module_component_id(null), inverter_component_id(null),
system_type, inputs(JSON), results(JSON), status('pass'|'warn'|'fail'),
confidence_score(int), confidence_band(str), created_at
```
`results` holds the entire engine `DesignReport` serialised — the frontend renders straight from it, so the
report shape is the API contract (§5.3).

**`chat_messages`**
```
id, session_key, role('user'|'assistant'|'system'), content, cards(JSON), attachments(JSON),
tool_trace(JSON), created_at
```
`session_key` for the dashboard is `"web:<uuid>"`, stored in `localStorage`. Telegram keeps using
`ConversationSession` keyed by chat id — the two share the orchestrator but not the transcript table.

---

## 4. The calculation engine (`backend/app/engine/`) — Agent A

Pure functions. Typed with `@dataclass(frozen=True)` inputs/outputs (defined in `engine/types.py`). Every module
below cites its spec section; **put the section number in the docstring** so a reviewer can trace it.

### 4.1 `constants.py` (spec §3, §7, §12)

- `BASE_EFFICIENCY = 0.75`, `SAFETY_FACTOR_LOAD = 1.20`, `TEMP_DERATING = 0.85`,
  `SIZING_MARGIN = 1.10`, `DEFAULT_PANEL_WP = 550`, `PANEL_FOOTPRINT_M2 = 2.1`,
  `LIFEPO4_DOD = 0.80`, `SYSTEM_VOLTAGE_DC = 48`, `COLD_VOC_BUFFER = 0.85`
- `DCAC_RATIO_MIN = 1.2`, `DCAC_RATIO_MAX = 1.5`, `DCAC_RATIO_DEFAULT = 1.25`
- `PSH_BY_STATE` — every state in spec §3.2 as `(low, high)`; helper `psh_for_state(state) -> (value, is_fallback)`
  returning the **midpoint** and a flag. Default `Selangor → 4.3`.
- `TILT_FACTORS` / `AZIMUTH_FACTORS` — the banded tables in spec §4 Stage 2D.
- `OBSTRUCTION_AREA_M2 = {"water_tank": 2.0, "aircon_compressor": 1.0, "solar_water_heater": 4.0}`
- `TNB_BLOCKS_DOMESTIC` (spec §12.1): `[(200, 21.80), (300, 33.40), (600, 51.60), (900, 54.60), (inf, 57.10)]` sen/kWh
- `CAPACITY_CHARGE_SEN = 4.55`, `NETWORK_CHARGE_SEN = 12.85`, `ICPT_SEN = 3.70`,
  `RETAIL_CHARGE_MYR = 10.0`, `RETAIL_CHARGE_WAIVER_KWH = 600`
- `TNB_RP4_GEN_SEN_LOW = 27.03` (≤1500 kWh), `TNB_RP4_GEN_SEN_HIGH = 37.03`
- `ATAP_SMP_MYR = 0.18`; `ATAP_DOMESTIC_RETAIL_RANGE = (0.27, 0.37)`; **export credit rollover = none**
- `STANDARD_GRIDTIE_KW = [3,4,5,6,8,10,12,15]`; `STANDARD_HYBRID_KW = [3.6,5,6,8,10,12]`
- `LFP_MODULES_KWH = [5.12, 10.24, 15.36]`
- `DEFAULT_MODULE_550W` — Vmp 41.5, Voc 49.6, Imp 13.2, Isc 14.0 (spec §12.5)
- `COST_RANGES_MYR` — spec §7 table, keyed `(system_type, tier)`
- `EQUIPMENT_BY_TIER` — spec §7 brand tables
- `USD_MYR_RATE = 4.72` (override via env `USD_MYR_RATE`)
- `CRITICAL_APPLIANCE_W` — spec §2.4 hybrid list

### 4.2 `site.py` (spec §4 Stage 2)

```python
effective_efficiency(tilt_deg, azimuth_deg, shading_factor) -> EfficiencyBreakdown
# 0.75 × tilt × azimuth × shading × 0.85 ; returns each factor for UI display
net_usable_area(roof_area_m2, obstructions) -> float
max_panels_from_roof(net_area_m2) -> int          # FLOOR(area / 2.1)
```
Azimuth > 90° from south ⇒ append a `WARN` flag, do not raise.

### 4.3 `array.py` (spec §5 Stages 1 & 3)

```python
design_daily_wh(monthly_kwh) -> float             # (monthly/30) × 1000 × 1.2
required_array_kwp(design_daily_wh, psh, eff) -> float
size_array(...) -> ArraySizing
```
`ArraySizing` carries: `required_kwp`, `max_roof_kwp`, `constrained: bool`, `coverage_pct`,
`final_kwp` (`required × 1.10` when unconstrained), `panel_count = CEIL(final×1000/wp)`,
`actual_kwp = panel_count × wp/1000`, plus self-consumption (spec §5 Stage 3C):
`daily_generation_kwh`, `self_consumed_kwh`, `exported_kwh`, `self_consumption_pct`,
and an `OVERSIZED` warning when exported > 30% of generation.

**EPC entry point (this is the demo path):** the field CV count is authoritative, so also expose
`array_from_panel_count(panel_count, module_wp, psh, eff)` which skips load-driven sizing and reports the
same struct with `required_kwp = None`. `run_design()` picks the branch: panel count present ⇒ CV path;
otherwise consumption-driven path.

### 4.4 `strings.py` (spec §4 Stage 6 / PRD 4.2) — **the money module**

```python
series_max(mppt_max_v, voc) -> int                 # FLOOR(mppt_max × 0.85 / Voc)
design_strings(panel_count, module, inverter) -> StringDesign
```
Search series counts from `series_max` downward for the largest that satisfies **all** of:
1. `vmp_string = series × Vmp` inside `[mppt_min_v, mppt_max_v]`
2. `voc_string = series × Voc < max_dc_voltage_v`
3. `parallel = CEIL(panel_count / series)`; `total_isc = parallel × Isc < max_input_current_per_mppt_a × mppt_count`

`StringDesign` returns `series`, `parallel`, `vmp_string`, `voc_string`, `voc_cold_string`, `total_isc`,
`panels_used = series × parallel`, `orphan_panels`, and `checks: list[Check]` where
`Check = {id, label, expected, actual, unit, passed, margin_pct}` — the UI renders these rows verbatim.
Status is `fail` when no series count satisfies all three; return the closest attempt with the failing checks
so the UI can explain *why*.

`voc_cold_string` uses the module's `temp_coeff_voc_pct_per_c` when known
(`Voc × (1 + coeff/100 × (T_cold − 25))`, `T_cold = 20 °C` for Malaysia); otherwise falls back to the flat
0.85 buffer. Report which method was used.

### 4.5 `inverter.py` (spec §5 Stage 4)

```python
target_ac_kw(array_kwp, ratio=1.25) -> float       # array / ratio
select_inverter(array_kwp, catalog, tier, system_type) -> InverterSelection
dc_ac_ratio(array_kwp, ac_kw) -> float
```
Selection = smallest catalog inverter whose `ac_rating_kw >= target_ac_kw` **and** `max_dc_input_kw >= array_kwp`
**and** whose resulting DC:AC lands in `[1.2, 1.5]`. Prefer brands from `EQUIPMENT_BY_TIER`. Emit a `Check` row
for the DC:AC band, for `max_dc_input_kw >= array_kwp`, and for anti-islanding presence.
When the manager names an inverter explicitly (demo: "standard 10kW Huawei string inverter"), **validate that one**
instead of selecting — `validate_inverter(array_kwp, panel_count, module, inverter)`.

### 4.6 `battery.py` (spec §6 — hybrid only)

```python
size_hybrid_battery(critical_load_w, backup_hours, dod=0.80, margin=1.12) -> BatteryDesign
```
Returns `raw_kwh`, `final_kwh`, `ah_at_48v`, `modules: [(count, module_kwh)]` from `LFP_MODULES_KWH`,
`c_rate`, and a `C_RATE` check (`≤ 0.8C`). Off-grid ⇒ raise `UnsupportedSystemType` (D5).

### 4.7 `bos.py` (spec §8 / PRD 4.3)

```python
generate_bos_spec(string_design, inverter, system_type) -> BosSpec
```
- **DC:** string fuse `ceil_to_standard(1.25 × Isc)` against `[10,12,15,16,20,25,30]` A;
  isolator rating `voc_string × 1.2` rounded up to `[600,800,1000,1100,1500]` V;
  Type 2 DC SPD, one per combiner; combiner box required when `parallel > 2`; reverse-polarity protection.
- **AC:** MCB from `I_ac = ac_kw × 1000 / (230 × 0.95)` single-phase (or `× √3 × 415` three-phase) rounded up to
  `[16,20,25,32,40,50,63,80,100]` A; Type 2 AC SPD; 30 mA RCCB; over/under-voltage; anti-islanding.
- **Earthing:** separate DC/AC, ≥16 mm Cu rod, 2.4 m, ≤5 Ω at commissioning.
- **Cables:** DC string 4 mm² (≤15 m, <20 A); DC battery 50 mm² (hybrid, ≤2 m); AC from a
  `CABLE_AMPACITY` table `[(4,32),(6,41),(10,57),(16,76),(25,101),(35,125),(50,151),(70,192),(95,232)]`
  picking the first ampacity ≥ `I_ac × 1.25`. Voltage drop budget ≤1.5% on every run.
- Each item is `{group, item, spec, rating, standard, note}` with `standard ∈ {"IEC 62548","IEC 60364","TNB TCG","MS IEC 60947"}`.

### 4.8 `financial.py` (spec §5 Stage 6, §12.1, §12.3 / PRD 4.4)

```python
tnb_bill_myr(kwh, category) -> BillBreakdown      # blocks + capacity + network + ICPT + retail
effective_tariff_myr_per_kwh(kwh, category) -> float
run_financials(array_kwp, psh, eff, monthly_kwh, system_cost_myr, tier) -> FinancialModel
```
- `monthly_generation_kwh = array_kwp × psh × eff × 30`
- `self_consumed = MIN(generation, consumption)`, `exported = MAX(0, generation − consumption)`
- `savings = self_consumed × effective_tariff + exported × ATAP_SMP_MYR` (**no rollover** — state it in the output)
- Payback `cost / annual_savings`, reported **as a range**: `(payback × 0.85, payback × 1.20)` rounded to 0.1 yr,
  never a single figure (spec §7 warning).
- Also return: `bill_before`, `bill_after`, `cost_range` from `COST_RANGES_MYR`, and a 25-year cumulative series
  `[{year, cumulative_savings, cumulative_net}]` with **0.5%/yr module degradation** and **3%/yr tariff escalation**
  (document both as assumptions in the output — they are not from the spec).

### 4.9 `confidence.py` (spec §9 / PRD 4.5 — **PRD bands win**)

```python
score_confidence(signals: ConfidenceSignals) -> ConfidenceScore
```
Additive, transparent, and **hard-capped at 94**:

| Component | Δ | Condition |
|-----------|---|-----------|
| Base | **85** | Panel count verified from a field photo + standard parameters |
| Supplier quote | **+3** | A parsed vendor quote is attached with real unit pricing |
| String validation | **+3** | String config validated PASS against a catalogued inverter |
| Site specifics | **+2** | Tilt/azimuth/shading recorded (not engine defaults) |
| Consumption | **+1** | Real monthly kWh on record |
| Manual count | **−10** | Panel count typed by hand, no field photo |
| PSH fallback | **−4** | State-average PSH with no site-specific irradiance |

`clamp(60, 94)`. Bands: `<80 "Indicative"`, `80–84 "Good estimate"`, `85–89 "Solid — suitable for quotation"`,
`90–94 "Detailed specification — installer to confirm string design"`.
Return `components: [{label, delta, applied, reason}]` so the UI shows the full breakdown on hover.
**Every** `ConfidenceScore` carries `disclaimer = "AI-estimated, installer-confirmed"`. Never emit 95+. Never emit 100.
Do not label outputs "AI-generated" in user-facing copy (PRD 2.2).

### 4.10 `report.py`

```python
run_design(inputs: DesignInputs) -> DesignReport
```
Single entry point, orchestrating §4.2 → §4.9 in the spec §10 order. Returns the serialisable `DesignReport`
(§5.3) with `warnings: list[Flag]` and `assumptions: list[str]` aggregated from every stage. This is the only
function `agents/tools.py` calls.

### 4.11 Tests — non-negotiable

`backend/tests/test_engine_*.py`, plain `pytest`. **Every worked example in the spec becomes an assertion:**

| Test | Source | Expect |
|------|--------|--------|
| effective efficiency | §4 Stage 2D | `0.75×1.00×0.98×0.95×0.85 ≈ 0.593` |
| roof max panels | §4 Stage 2 | 42 m² − 2 m² ⇒ 19 panels, 10.45 kWp |
| on-grid array sizing | §5 Stage 3 | 363 kWh/mo ⇒ 14,520 Wh/day ⇒ 5.44 kWp req ⇒ 11 panels ⇒ 6.05 kWp |
| self-consumption | §5 Stage 3C | 16.14 kWh gen, 14.52 self, 1.62 exported (~10%, acceptable) |
| inverter select | §5 Stage 4 | 6.05 kWp ÷ 1.5 ⇒ 4.03 kW ⇒ selects 4 kW |
| **string design** | §4 Stage 6 | Longi 550W + 120–500 V MPPT ⇒ series_max 8; 3S×5P **for exactly 15 panels**; Vmp 124.5 V; Voc 148.8 V; Isc 70 A — all pass (this is the spec's own illustrative panel count, not the demo's) |
| **PRD demo case** | PRD §6 | **Corrected 2026-08-31** — the PRD narrative's "3S×5P" line is the spec's 15-panel worked example copy-pasted into a 20-panel scenario; it is unreachable for 20 panels against a 120–500 V MPPT window (raising series always *lowers* Isc, so the algorithm always resolves to `series_max`=8, regardless of panel count — verified empirically, see `checkpoints/PHASE_1A_ENGINE.md`). Actual computed result for 20 panels / Longi Hi-MO7 550W / Huawei SUN2000-10KTL-M1: **8S × 3P**, Vmp 332 V, Voc 396.8 V (well inside the 500 V window and 1080 V absolute max), DC:AC 1.1, BOS fuse 20 A, confidence 91, status `pass` with an `ORPHAN_PANELS` warning (4 panels short of a full third string). Use these numbers in the demo script and every UI fixture — they are what `run_design()` actually returns, and that traceability is the point.|
| financial | §5 Stage 6 | 484 kWh/mo; ~RM 204 self + RM 9 export ≈ RM 213/mo; payback ≈ 9.8 yr shown as a range |
| BOS fuse | §8 | 14.0 A Isc ⇒ 1.25× = 17.5 A |
| confidence cap | §9 | never > 94 under any signal combination |

Use `pytest.approx(rel=0.02)` for float comparisons. If a spec worked example disagrees with the spec's own formula,
**follow the formula** and note the discrepancy in a test comment.

---

## 5. API contract (Agent C builds it, Agent D consumes it)

Base `http://localhost:8000`. All new endpoints under `/api`. Existing routes stay untouched.

### 5.1 REST

| Method | Path | Body / Query | Returns |
|--------|------|--------------|---------|
| `GET` | `/api/overview` | — | Fleet KPIs: `total_capacity_kwp`, `active_projects`, `open_rfqs`, `po_value_myr`, `avg_confidence`, `panels_installed`, `co2_avoided_tonnes`, plus 12-month `generation_trend` and `spend_trend` |
| `POST` | `/api/uploads` | multipart `file` | `{file_id, filename, url, kind:"pdf"\|"image"\|"audio", size}` |
| `POST` | `/api/quotes/parse` | `{file_id, project_id?}` | `SupplierQuote` + line items (§5.4) |
| `GET` | `/api/quotes` / `/api/quotes/{id}` | — | list / detail |
| `POST` | `/api/feasibility/run` | `FeasibilityRequest` (§5.2) | `DesignReport` (§5.3) |
| `GET` | `/api/feasibility/{id}` | — | stored run |
| `GET` | `/api/feasibility?project_id=` | — | run history |
| `GET` | `/api/components` | `?kind=&q=&limit=` | catalog rows |
| `GET` | `/api/bnef/check?manufacturer=` | — | `{manufacturer, tier1: bool, matched_name, source}` |
| `POST` | `/api/po/generate` | `{feasibility_run_id, vendor_id?, notify_telegram: bool}` | `{po, pdf_url, telegram_sent}` |
| `POST` | `/api/voice/transcribe` | multipart `audio` | `{text, duration_s, language}` |
| `POST` | `/api/voice/speak` | `{text, voice_id?}` | `audio/mpeg` |
| `GET` | `/api/chat/history?session_key=` | — | `ChatMessage[]` |
| `POST` | `/api/chat` | `{session_key, message, attachments?}` | non-streaming fallback: `{reply, cards}` |
| `POST` | `/api/chat/stream` | same | **SSE** (§5.5) |

Existing: `/projects`, `/vendors`, `/inspections`, `/invoices`, `/purchase-orders`, `/analytics/*`,
`/events` (SSE activity feed), `/webhook/telegram`. Keep them working.

### 5.2 `FeasibilityRequest`

```jsonc
{
  "project_id": 1,
  "system_type": "on_grid",           // on_grid | hybrid
  "panel_count": 20,                  // optional — defaults to project's latest inspection count
  "module": { "component_id": 12 },   // OR {"manufacturer","model","rated_wp","vmp","voc","imp","isc"}
  "inverter": { "component_id": 44 }, // OR inline specs; omit to auto-select
  "quote_id": 7,                      // optional — pulls pricing + real module specs
  "monthly_consumption_kwh": 950,     // optional override of the project value
  "system_cost_myr": 25000,           // optional; else derived from quote or COST_RANGES_MYR
  "budget_tier": "mid",               // entry | mid | premium
  "backup_hours": 4,                  // hybrid only
  "critical_appliances": ["refrigerator","lights","wifi_router","fans"]
}
```

### 5.3 `DesignReport` — the shape everything renders from

```jsonc
{
  "id": 12, "project_id": 1, "system_type": "on_grid", "status": "pass",
  "generated_at": "2026-08-31T09:12:00Z",
  "confidence": { "score": 92, "band": "Detailed specification — installer to confirm string design",
                  "disclaimer": "AI-estimated, installer-confirmed",
                  "components": [{ "label": "Parsed supplier quote", "delta": 3, "applied": true, "reason": "..." }] },
  "site": { "state": "Selangor", "psh": 4.3, "psh_source": "state_average",
            "roof_area_m2": 42, "net_area_m2": 40, "max_panels": 19,
            "efficiency": { "base": 0.75, "tilt": 1.0, "azimuth": 0.98, "shading": 0.95,
                            "temperature": 0.85, "effective": 0.593 } },
  "load": { "monthly_kwh": 950, "daily_kwh": 31.7, "design_daily_wh": 38000, "safety_factor": 1.2 },
  "array": { "panel_count": 20, "module": { "manufacturer": "Longi", "model": "Hi-MO7 LR5-72HTH-550M",
             "rated_wp": 550, "vmp": 41.5, "voc": 49.6, "imp": 13.2, "isc": 14.0, "bnef_tier1": true },
             "actual_kwp": 11.0, "required_kwp": 9.4, "max_roof_kwp": 10.45,
             "constrained": false, "coverage_pct": 100,
             "daily_generation_kwh": 28.06, "self_consumed_kwh": 28.06,
             "exported_kwh": 0, "self_consumption_pct": 100 },
  "strings": { "series": 8, "parallel": 3, "config_label": "8S × 3P", "panels_used": 24, "orphan_panels": 4,
               "vmp_string": 332.0, "voc_string": 396.8, "voc_cold_string": 396.8,
               "voc_method": "flat_0.85_buffer", "total_isc": 42.0,
               "checks": [{ "id":"vmp_in_mppt", "label":"String Vmp within MPPT window",
                            "expected":"120–500 V", "actual":332.0, "unit":"V",
                            "passed":true, "margin_pct":33.6 }] },
  "inverter": { "manufacturer":"Huawei", "model":"SUN2000-10KTL-M1", "ac_rating_kw":10,
                "max_dc_input_kw":15, "mppt_min_v":120, "mppt_max_v":500, "max_dc_voltage_v":1080,
                "dc_ac_ratio":1.1, "selected_by":"user", "checks":[ ... ] },
  "battery": null,                         // hybrid only
  "bos": { "groups": [{ "group":"DC Protection",
                        "items":[{ "item":"String DC fuse", "spec":"1.25 × Isc per string",
                                   "rating":"20 A gPV", "standard":"IEC 62548",
                                   "note":"Calculated 17.5 A → next standard size" }] }] },
  "financial": { "monthly_generation_kwh": 842, "effective_tariff_myr": 0.4713,
                 "monthly_savings_myr": 397, "annual_savings_myr": 4764,
                 "bill_before_myr": 448, "bill_after_myr": 51,
                 "system_cost_myr": 44000, "cost_range_myr": [35000, 50000],
                 "payback_years": 9.2, "payback_range_years": [7.8, 11.0],
                 "export_kwh": 0, "export_rate_myr": 0.18, "rollover": false,
                 "projection": [{ "year":1, "cumulative_savings":4764, "cumulative_net":-39236 }],
                 "assumptions": ["0.5%/yr module degradation", "3%/yr tariff escalation", "No export credit rollover (Solar ATAP)"] },
  "equipment_tier": "premium",
  "warnings": [{ "level":"warn", "code":"ORPHAN_PANELS", "message":"Last string is 4 panels short of a full 8S string at this series count — consider a second MPPT input or a lower series count" }],
  "assumptions": ["Temperature derating 0.85 fixed for Malaysian ambient", "..."]
}
```

Frontend rule: **never recompute a number from this payload.** Render what is there. If a field is missing, show
an em-dash, not a guess.

### 5.4 `SupplierQuote` response

```jsonc
{ "id": 7, "supplier_name_raw": "SunTech Materials Sdn Bhd", "vendor_id": 3, "vendor_matched": true,
  "source_filename": "quote-suntech-aug26.pdf", "currency": "MYR", "fx_rate_to_myr": 1.0,
  "parse_status": "parsed", "page_count": 2, "subtotal_myr": 51240.00,
  "parse_notes": "Line 4 unit ambiguous ('nos') — assumed pieces.",
  "line_items": [
    { "line_no":1, "category":"module", "manufacturer":"Longi", "model":"Hi-MO7 LR5-72HTH-550M",
      "description":"550Wp N-type TOPCon monocrystalline module", "quantity":20, "unit":"pcs",
      "unit_price":467.00, "currency":"MYR", "unit_price_myr":467.00, "line_total_myr":9340.00,
      "rated_wp":550, "price_per_wp_myr":0.849, "warranty_years":25, "lead_time_days":21,
      "bnef_tier1":true, "tier_match_name":"LONGi Green Energy", "flags":[] }
  ],
  "summary": { "total_wp":11000, "blended_price_per_wp_myr":0.849, "tier1_line_count":1, "flagged_line_count":0 } }
```

### 5.5 SSE event protocol — `POST /api/chat/stream`

`text/event-stream`, one JSON object per `data:` line. Event `type`:

| `type` | Payload | UI behaviour |
|--------|---------|--------------|
| `status` | `{label, phase}` | Animated status line ("Reading page 2 of 3…") |
| `tool` | `{name, args}` | Tool chip appears in the trace strip, spinner on |
| `tool_result` | `{name, ok, summary, ms}` | Chip resolves to a check or a cross with elapsed ms |
| `delta` | `{text}` | Append to the streaming assistant bubble |
| `card` | `{card_type, data}` | Mount a rich card (§6.4) with an entrance animation |
| `warning` | `{level, message}` | Inline callout |
| `done` | `{message_id, cards:[…]}` | Finalise, persist, re-enable composer |
| `error` | `{message}` | Error bubble with a retry affordance |

`card_type ∈ {quote_parsed, feasibility, bos_spec, financial, confidence, po_draft, project_summary, vendor_list, rfq_status, component_pick}`.

Heartbeat `:\n\n` comment every 15 s so proxies don't kill the stream.

### 5.6 New orchestrator tools (`agents/tools.py`)

| Tool | Args | Notes |
|------|------|-------|
| `parse_supplier_quote` | `file_id, project?` | Delegates to Agent B. Emits a `quote_parsed` card. |
| `run_feasibility` | `project, panel_count?, module?, inverter?, quote_id?, system_type?` | Calls `engine.report.run_design`. Emits `feasibility` + `confidence` cards. |
| `generate_bos_spec` | `feasibility_run_id` | Re-emits the stored BOS as its own card. |
| `financial_analysis` | `project` or `feasibility_run_id`, `system_cost?` | Emits `financial` card. |
| `list_components` | `kind, brand?, q?` | Catalog search. |
| `check_bnef_tier` | `manufacturer` | Registry lookup. |
| `generate_po_package` | `feasibility_run_id, vendor?` | Creates the PO, renders the PDF, pushes to Telegram. |

**System-prompt additions** (append to the existing prompt, keep the domain lock and the anti-fabrication rules):

> You never calculate. Voltages, currents, string counts, fuse ratings, savings, payback and confidence come only
> from tool results — quote them exactly as returned and never round or recompute them. When a tool returns a card,
> the UI is already showing it: your text must add context or a next step, not repeat the numbers.

Bump `MAX_TOOL_ROUNDS` 5 → 8 (a feasibility chain is parse → feasibility → financial → PO).
Set `LLM_TEXT_MODEL=qwen-plus` — `qwen-turbo` is too weak for a 7-tool chain. Note it in `.env.example`.

---

## 6. Frontend architecture (Agent D)

### 6.1 Dependencies (orchestrator adds these; do not add more)

`motion` (Framer Motion v12) · `lucide-react` · `clsx` · `tailwind-merge`.
**Charts are hand-rolled SVG.** No Recharts/Chart.js — a charting library is what makes a dashboard look
templated, and the PRD wants this to look like a product.

### 6.2 Design system — `src/design/tokens.css`

Semantic CSS custom properties on `:root`, overridden under `[data-theme="dark"]`, with `prefers-color-scheme`
as the default when no explicit choice is stored. **Never** hardcode a hex in a component.

```
--bg, --bg-subtle, --bg-elevated, --surface, --surface-hover, --border, --border-strong,
--text, --text-muted, --text-subtle, --accent, --accent-hover, --accent-fg,
--success, --warning, --danger, --info,
--chart-1..--chart-6, --shadow-sm, --shadow-md, --shadow-lg, --radius-sm/md/lg/xl
```

Direction: **solar-industrial.** Dark = near-black `#0A0B0D` canvas, elevated `#121418` panels, hairline
`#1F232A` borders, solar-amber `#FFB020` primary accent, electric-lime `#A3E635` for "generating/pass" states.
Light = `#FAFAF9` canvas, white panels, `#0C0E12` ink, same accent hues darkened ~12% for AA contrast.
Both palettes must pass **WCAG AA (4.5:1)** for body text — verify, don't assume.

Type: one display face for numerals and headings + system sans for body. Tabular numerals
(`font-variant-numeric: tabular-nums`) on **every** metric so digits don't jitter while streaming.

Motion: `--ease-out: cubic-bezier(0.16,1,0.3,1)`; durations 120/200/320 ms. Everything respects
`prefers-reduced-motion` — that check is a hard requirement, not a nicety.

### 6.3 Routes

| Path | Screen |
|------|--------|
| `/` | **Command Center** — KPI rail, generation-vs-consumption chart, live activity feed, project heatmap, docked AI chat |
| `/feasibility` | Engineering workbench — component pickers, string diagram, check matrix, BOS spec, confidence badge |
| `/procurement` | Quote inbox — drop zone, parsed quotes, RM/Wp comparison table, RFQ batch tracker |
| `/projects`, `/projects/:id` | Existing, restyled; project detail gains Design, Quotes, Financials tabs |
| `/vendors` | Existing, restyled; adds BNEF tier + brands-carried columns |
| `/purchase-orders` | Existing, restyled |
| `/components` | Catalog browser for the CEC module/inverter tables |

### 6.4 Component inventory

**Primitives** (`components/ui/`): `Button`, `IconButton`, `Card`, `Badge`, `Tooltip`, `Tabs`, `Sheet`, `Dialog`,
`Skeleton`, `Toast`, `Progress`, `Segmented`, `Table`, `EmptyState`, `ThemeToggle`, `CommandPalette` (⌘K).

**Charts** (`components/charts/`, hand-rolled SVG, responsive via `ResizeObserver`):
`AreaChart` (gradient fill, hover crosshair, animated path draw-in), `BarChart`, `RadialGauge` (confidence),
`RangeMeter` (DC:AC ratio band with a pass zone), `Sparkline`, `MpptWindowBar` (string Vmp/Voc inside the
inverter window — the single most persuasive graphic in the demo).

**Chat** (`components/chat/`): `ChatPanel` (dockable, resizable, full-screen), `MessageList`,
`Composer` (multiline, `⌘↵`, paste-to-upload), `Dropzone` (whole-panel drag overlay), `MicButton`
(press-and-hold, live waveform from `AnalyserNode`, cancel-on-drag-away), `ToolTrace` (collapsible chips),
`StreamingText` (character reveal), `SuggestionChips` (seeded with the demo prompts).

**Cards** (`components/cards/`), one per `card_type` in §5.5:
`QuoteCard` (line-item table, RM/Wp pill, animated Tier-1 badges, flagged rows in warning),
`FeasibilityCard` (`StringDiagram` — animated SVG of series×parallel panel blocks wiring into the inverter —
plus the check matrix), `BosSpecCard` (grouped checklist, copy-as-markdown, IEC refs),
`FinancialCard` (savings headline, payback range bar, 25-yr cumulative area chart, before/after bill),
`ConfidenceBadge` (radial gauge + breakdown popover + mandatory disclaimer),
`PoCard` (Approve & Generate PO → Telegram dispatch with a success state).

### 6.5 Non-negotiables

1. **Loading is designed, not spun.** Skeletons matching final layout; the chat shows real phase labels from
   `status` events.
2. **Empty states are designed.** Every list has an illustrated empty state with an action.
3. **Keyboard.** ⌘K palette, `/` focuses chat, `Esc` closes overlays, visible focus rings throughout.
4. **Responsive** down to 768 px (judges may view on a laptop or a tablet). Chat becomes a bottom sheet.
5. **No layout shift** when cards stream in — reserve space, animate opacity+transform only.
6. **`prefers-reduced-motion`** disables all non-essential motion.
7. Confidence is **never** shown without the "AI-estimated, installer-confirmed" disclaimer adjacent.
8. Nothing is labelled "AI-generated" in user-facing copy (PRD 2.2).

---

## 7. Messy supplier quote PDF (Agent B)

`backend/scripts/generate_messy_quote.py` — CLI: `--vendor <id|name> --project <id|name> --out <path> --seed N`.

Reads **real** `Vendor` rows (name, email, region, `brands_carried`, `quote_currency`, `on_time_rate`,
`unit_price_myr`) and **real** `components` rows for the models quoted, so every value traces to the database.

Deliberate messiness — it must be genuinely hard to parse, or the demo proves nothing:
- Letterhead with a fake registration number, GST/SST line, and a bank-details block
- Line items in an **inconsistent** table: some rows merged, one row wrapping to two lines, misaligned columns
- **Mixed units**: `pcs`, `nos`, `units`, `set`, `lot`
- **Mixed currency**: 1–2 line items in USD with a footnote "USD converted at 4.72" (exercises normalisation)
- Wattage buried in the description text, not its own column ("550Wp N-type TOPCon")
- Warranty and lead time in a **free-text footnote**, not columns
- Incoterms ("FOB Port Klang", "Ex-works Shah Alam") and a validity clause
- A handwritten-style annotation ("subject to stock — pls confirm by Fri") at a slight rotation
- Page break mid-table with repeated headers
- One typo and one inconsistent model-number format
- Faint scan-like grey background and a rotated "RECEIVED" stamp

Also emit `backend/uploads/quotes/` fixtures at seed time so the demo never depends on running the script live.
**Ship at least 3 pre-generated quotes from 3 different seeded vendors, one of them USD.**

---

## 8. Voice (Agent C)

`services/voice.py`, plain `httpx` — no SDK.

- **STT:** `POST https://api.elevenlabs.io/v1/speech-to-text`, multipart `file` + `model_id` (default `scribe_v1`,
  override via `ELEVENLABS_STT_MODEL`), header `xi-api-key`. Returns `{text, language_code}`.
- **TTS:** `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128`,
  `{text, model_id: "eleven_turbo_v2_5"}`. Default voice via `ELEVENLABS_VOICE_ID`.
- **No key ⇒ stub:** STT returns a fixed field note, TTS returns 204. The app must stay fully runnable — same
  discipline as the existing Telegram/SMTP stubs.
- **Telegram:** `webhook.py` gains `voice` / `audio` / `video_note` handling → `getFile` → download → transcribe →
  feed the transcript into the normal router as the message body, and prefix the reply with the transcript so the
  field engineer can see what was heard.

New env (append to `.env`, document in `README.md`):
```
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
ELEVENLABS_STT_MODEL=scribe_v1
USD_MYR_RATE=4.72
```

---

## 9. Seed data policy

**The existing database is the source of truth.** `seed.py` must remain idempotent-by-recreate and keep the current
4 projects, 6 vendors, their POs, invoices, and inspections **with identical names, emails, and figures**.

Additive only:
- Backfill the new `Project` columns with realistic values (Johor Bahru commercial ~4,800 kWh/mo;
  Sungai Petani domestic ~780; Kuching commercial ~3,100; Greenfield/KL Tech Park left for the live demo).
- Backfill `Vendor.bnef_tier` / `brands_carried` — make **one** vendor Tier 2 so the warning badge has a real subject.
- Seed `components` from `app/data/cec_modules.csv` + `app/data/cec_inverters.csv`.
- Optionally add 2 new vendors that carry inverters/batteries if the existing 6 can't cover the demo — additive,
  never replacing.

`reset_demo.py` must clear the new transactional tables (`supplier_quotes`, `quote_line_items`,
`feasibility_runs`, `chat_messages`) alongside the existing ones — but **not** `components`.

---

## 10. Risks

| Risk | Mitigation |
|------|-----------|
| `qwen-turbo` too weak for a 7-tool chain | Switch to `qwen-plus`; force `tool_choice` for quote-parse and feasibility intents as the existing code already does for procurement |
| Vision parse returns malformed JSON | Strict schema in the prompt + `_parse_json_response` repair + one retry at temperature 0 + `parse_status:"partial"` rather than a hard failure |
| SQLite lacks migrations | Idempotent `ALTER TABLE ADD COLUMN` runner in `db_upgrade.py`, guarded by `PRAGMA table_info` |
| Live demo network failure | Pre-generated quote fixtures, cached feasibility runs, stub paths for every external service |
| Parallel agents colliding | Strict ownership map (§2); shared files written by the orchestrator only |
| Frontend built against a moving contract | This document freezes the contract; Agent D develops against `frontend/src/lib/fixtures.ts` mirroring §5.3 |

---

## 11. Definition of done

- [ ] `pytest backend/tests` green, including every spec worked example in §4.11
- [ ] `npm run build` clean (no TS errors, no unused imports)
- [ ] The full PRD §6 four-minute script runs end to end without a manual DB edit
- [ ] Light and dark both audited at AA contrast
- [ ] No confidence value above 94 reachable by any input
- [ ] Existing Telegram inspection + RFQ email flows still pass `DEMO_CHECKLIST.md`
- [ ] `CHECKPOINTS.md` fully ticked with file-level evidence
