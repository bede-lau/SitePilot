# Phase 1A — Calculation Engine (Agent A) — checkpoint

Status: **complete**. `backend/app/engine/**`, `backend/app/data/**`, `backend/tests/test_engine_*.py`,
`backend/tests/__init__.py`, `backend/pytest.ini` all landed. Full `pytest backend/tests` is green
(113 tests) and the whole app (`app.main`) still imports cleanly.

## What existed before this session (45%, untouched)

`engine/types.py`, `engine/constants.py`, `engine/site.py`, `engine/array.py`, `engine/strings.py`,
`tests/test_quote_parser.py` (Agent B's, still green — 38 tests, unmodified).

## What this session built

### `backend/app/data/bnef.py` (+ `backend/app/data/__init__.py`)
`match_manufacturer(name) -> (is_tier1, matched_name)`. ~40 real BNEF Tier 1 module manufacturers
(LONGi, Trina, JA Solar, Jinko, Canadian Solar, Risen, Astronergy, First Solar, Qcells, GCL, Tongwei,
DAS Solar, Boviet, Waaree, Vikram, Adani, ZNShine, Suntech, HT-SAAE, Talesun, Phono, Emmvee, REC,
Seraphim, Yingli, Sunpower/Maxeon, Jolywood, ... ) plus 7 explicit Tier 2 names (Sunport, Amerisolar,
Eurener, Perlight, Topray, Sunrise Energy, Goldi). Normalisation strips punctuation, casing, and
corporate suffixes (Sdn Bhd, Co Ltd, GmbH, Inc, Pte, Ltd, ...) iteratively, then does an exact-match
lookup with a substring fallback. Verified against "LONGi Green Energy Technology Co., Ltd." / "Longi
Solar" / "LONGI" all resolving to the same canonical entry, and unknown names returning `(None, None)`.
This unblocked `agents/quote_parser.py`, `agents/tools.py`, `routes/components.py` (all three already
had `try/except ImportError` guards against it landing late — those now resolve to real lookups).

### `engine/inverter.py` — ARD §4.5
`target_ac_kw`, `dc_ac_ratio`, `select_inverter(array_kwp, catalog, tier, system_type) ->
tuple[InverterSpec, InverterSelection]`, `validate_inverter(array_kwp, inverter) -> InverterSelection`.

**Deviation from ARD's literal signature:** `select_inverter` returns `(chosen InverterSpec,
InverterSelection)` instead of just `InverterSelection` — the frozen `InverterSelection` output type in
`types.py` doesn't carry `max_input_current_per_mppt_a` / `mppt_count` / `phase`, which
`strings.design_strings` and `bos.generate_bos_spec` need afterwards. `report.py` needs the raw spec in
hand, not just the summary. `validate_inverter` only takes `(array_kwp, inverter)` — no `panel_count`/
`module` params — since the caller already holds the `InverterSpec` in that case (string-level checks
live in `strings.validate_inverter`, already built, unchanged).

### `engine/battery.py` — ARD §4.6 (hybrid only)
`size_hybrid_battery(critical_load_kw, backup_hours, dod=0.80, margin=constants.BATTERY_SAFETY_MARGIN_HYBRID)
-> BatteryDesign`. `UnsupportedSystemType` exception defined here, raised by `report.py` immediately for
any `system_type == "off_grid"` request (ARD D5).

**Deviation from ARD's stated default margin (1.12):** that figure is the *off-grid* margin (spec §4
Stage 4B). This module is hybrid-only; the spec's own hybrid worked example (§6 Stage 5C) and the
already-landed `constants.BATTERY_SAFETY_MARGIN_HYBRID` both say **1.10** — used that instead.

C-rate guard grows the battery (never shrinks it) when the naive margin-adjusted capacity would exceed
0.8C. Module selection picks the smallest standard LFP size (5.12/10.24/15.36 kWh) that covers the
requirement, stacking multiples of the largest size if the requirement exceeds it.

### `engine/bos.py` — ARD §4.7
`generate_bos_spec(string_design, inverter, system_type) -> BosSpec`, 4 groups (DC Protection, AC
Protection, Earthing, Cables). `inverter` here is the raw `InverterSpec` (not `InverterSelection`) —
BOS needs `phase` and `has_anti_islanding`, which aren't in the output-summary type. `module_isc` is
recovered exactly as `string_design.total_isc / string_design.parallel` rather than being passed
separately. Standards mapping (IEC 62548 / IEC 60364 / TNB TCG / MS IEC 60947 per item) is an
engineering judgment call — the spec names the allowed set but doesn't map every item to one.

### `engine/financial.py` — ARD §4.8
`tnb_bill_myr`, `effective_tariff_myr_per_kwh`, `run_financials`. Self-consumption split uses the same
"design daily" (safety-factor-inflated) baseline as `array.py`'s Stage 3C check, for internal
consistency between the `array` and `financial` sections of one report. Commercial tariff uses the flat
RP4 generation-charge bands (no published block schedule exists for commercial in the spec) with the
same capacity/network/ICPT/retail add-ons layered on top as domestic.

**Deviation:** the spec's own worked example ("effective tariff RM 0.47", "RM 204 self + RM 9 export ≈
RM 213/mo") is a rounded illustrative figure from the separate §12.2 blended-rate table, not derived
from the §12.1 block formula. Followed the formula (`tnb_bill_myr`) instead of hard-coding RM 0.47 —
documented at length in the module docstring and in `test_engine_financial.py`.

### `engine/confidence.py` — ARD §4.9
Additive model, hard-capped `[60, 94]`, never 95+/100 — verified by an exhaustive test over all 2^6
signal combinations (`test_confidence_never_exceeds_94_under_any_signal_combination`). `components`
reports every row (applied or not), matching "so the UI shows the full breakdown on hover."

### `engine/report.py` — ARD §4.10
`run_design(inputs: DesignInputs) -> DesignReport`. Orchestrates site → load/array → inverter → strings
→ battery (hybrid) → BOS → confidence → financial, in that order, aggregating `warnings`/`assumptions`
from every stage.

**Status aggregation — the one substantive design decision made here, not spec-cited:** ARD §5.3's own
worked example shows `"status": "pass"` *coexisting* with an `ORPHAN_PANELS` warning — proving warnings
don't automatically downgrade status. `status` is `"fail"` only if string design fails or a *critical*
inverter check fails (`max_dc_input_kw`, `anti_islanding`); `"warn"` only for a curated subset of
degradation codes (`ROOF_CONSTRAINED`, `PANEL_COUNT_EXCEEDS_ROOF`, `AZIMUTH_SUBOPTIMAL`); everything
else (DC:AC ratio outside the ideal band, orphan panels, oversized export) surfaces in `warnings` but
leaves `status` at `"pass"`. Without this, the PRD demo case (see below) would report `"warn"`, contrary
to the ARD §4.11 test table's explicit "status pass" requirement.

### `backend/app/data/cec_modules.csv` (45 rows) / `cec_inverters.csv` (37 rows)
Headers match ARD §3.3 / `seed.py`'s primary field-alias spelling exactly (verified by loading through
`seed.py`'s actual `_load_components_from_csv`, not just eyeballing the CSV). Contains the two
demo-critical exact rows verified byte-for-byte against the team brief:
- `Longi / Hi-MO7 LR5-72HTH-550M`: 550 Wp, Vmp 41.5, Voc 49.6, Imp 13.2, Isc 14.0
- `Huawei / SUN2000-10KTL-M1`: 10 kW AC, MPPT 120–500 V, max DC 1080 V, three-phase

Plus Trina Vertex N/S+, JA Solar DeepBlue, Risen Titan, Canadian Solar HiKu6/7, Jinko Tiger Neo,
Astronergy ASTRO N, and a handful more (DAS Solar, Boviet, Waaree, Adani, ZNShine, Qcells) spanning
400–630 Wp, PERC and TOPCon. Inverters cover Huawei, Sungrow, Solis, Growatt, Deye, SMA, Fronius,
GoodWe from 3–15 kW, both grid-tie and hybrid-labelled models (real product-family naming; the DB schema
has no explicit hybrid/on-grid flag on `Component`, so hybrid-capability isn't itself a queryable field
— matches what `feasibility_engine.py` already expects).

## Tests (113 passed, 0 skipped, 0 xfail)

`test_engine_site.py` (12), `test_engine_array.py` (7), `test_engine_strings.py` (9),
`test_engine_inverter.py` (5), `test_engine_battery.py` (4), `test_engine_bos.py` (7),
`test_engine_financial.py` (10), `test_engine_confidence.py` (7), `test_engine_report.py` (9) — every
ARD §4.11 table row has a corresponding assertion. Plus `test_quote_parser.py` (38, Agent B's, untouched
and still green).

```
$ cd backend && PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q
113 passed in 1.16s
```

```
$ cd backend && venv/Scripts/python.exe -c "from app.engine.report import run_design; print('ok')"
ok
$ venv/Scripts/python.exe -c "import app.main; print('app.main ok')"
app.main ok
```

## ⚠ Important finding: a real spec-vs-algorithm conflict (flagged, not silently resolved)

**The PRD §6 demo's expected string config (3S × 5P, Vmp 124.5 V, Voc 148.8 V) is unreachable** for the
required Huawei SUN2000-10KTL-M1 pairing (MPPT window 120–500 V, as mandated), given the *already-built*
`strings.design_strings` algorithm (ARD §4.4: "search series counts from series_max downward for the
**largest** that satisfies all checks").

Root cause: raising the series count for a *fixed panel count* strictly lowers the number of parallel
strings needed, which strictly lowers total Isc — so every one of the three validation checks gets
*easier*, not harder, at a higher series count, for any inverter with a wide MPPT window. There is no
per-string current limit that makes the algorithm choose 3 over 8 when `mppt_max_v = 500`; it will
always return `series_max` itself (computed as `FLOOR(500 × 0.85 / 49.6) = 8`), independent of panel
count. I verified this empirically (not just by hand-derivation) by sweeping `max_input_current_per_mppt_a`
from 13 A to 40 A against both 15 and 20 panels — every value that lets the spec's claimed 70 A "pass"
also lets series=8 pass, because series=8 needs *less* current headroom, not more.

The spec's own §4 Stage 6 worked example *itself* computes `series_max = 8` and then says "→ Use 3
series (practical for 48V system)" — a human judgment call never formalised into the three stated
checks. ARD §4.4 turned "which series count" into an explicit algorithm, and that algorithm doesn't
reproduce the spec author's manual pick whenever the MPPT window is this wide (confirmed: this isn't
specific to the Huawei model or to 20 vs. 15 panels — it's structural).

**What I did:** left `strings.py` untouched (outside my file ownership, and it correctly implements what
ARD §4.4 literally specifies). Verified the algorithm *does* reproduce the spec's exact worked numbers
(124.5 V / 148.8 V / 3S×5P / 70 A, all checks passing) once the inverter's MPPT window is narrow enough
that `series_max` itself computes to 3 (`test_string_design_narrow_mppt_window_matches_worked_example`)
— so the algorithm itself is not broken, it's just structurally incompatible with a *wide* MPPT window
plus "always prefer the largest valid series." For the actual demo pairing, `run_design()` currently
returns `8S × 3P` (Vmp 332 V, Voc 396.8 V) for 20 panels — asserted directly in
`test_engine_report.py::test_prd_demo_case`, with the discrepancy documented at length in both that file
and `test_engine_strings.py`.

**What still holds for the demo, verified exactly as ARD §4.11 lists it:** overall `status: "pass"`
(after the warnings-vs-status fix described above), DC:AC ratio 1.1 (within `[1.0, 1.5]`), confidence 91
(within `[90, 94]`), BOS string fuse 20 A (17.5 A calculated → next standard size) — none of those four
depend on which series count wins, so the rest of the demo script (BOS spec, confidence badge, financial
figures, PO generation) is unaffected.

**This needs a product/orchestrator decision**, not something I should silently paper over by narrowing
the Huawei's MPPT window below the required "~120–500V" (which would both violate the exact-parts
requirement and misrepresent the real inverter) or by hand-editing `strings.py`'s selection rule (outside
my ownership, and might have knock-on effects on other already-passing behaviour). Two real options for
whoever owns the demo narrative / `strings.py`: (a) change the demo script's stated numbers to match
`8S × 3P` / 332 V / 396.8 V (still passes every check, still a clean `MpptWindowBar` visual, just a
different number), or (b) change the selection algorithm to prefer the *lowest* series count that
passes all checks (closer to real-world practice of minimising string voltage stress) rather than the
highest — which would also flip the narrow-window test case's `3S×5P` result to something else only if a
lower series count also passes there, so that change should be re-verified against both scenarios if
made.

## Other ambiguities resolved (minor, all documented at the point of decision)

- **BOS standard-to-item mapping** (`IEC 62548` / `IEC 60364` / `TNB TCG` / `MS IEC 60947`): the spec
  names the allowed set but doesn't map every item; assigned by engineering judgment in `bos.py`.
- **Confidence "site specifics recorded"**: any of tilt/azimuth/shading being non-null (not all three
  required).
- **Hybrid critical appliances defaulting**: when `critical_appliances` is empty for a hybrid request,
  defaults to the spec's own §6 Stage 4A example set (fridge + lights + router + fans) rather than
  producing a degenerate zero-capacity battery; noted in `assumptions`.
- **Backup hours defaulting**: missing `backup_hours` for hybrid defaults to 4 hrs ("rarely", per
  `constants.BACKUP_HOURS_BY_FREQUENCY`), noted in `assumptions`.
- **Battery aircon worked example** (spec §6 Stage 5, second example): the spec's shown text skips the
  ×1.10 margin step for this one example (unlike the first, which shows it explicitly) and picks a
  single 15.36 kWh module from the *raw* 14.4 kWh figure. Followed the formula consistently (always
  apply the margin), which pushes the requirement to 15.84 kWh — just over the largest single module —
  so the engine stacks two 15.36 kWh modules rather than under-sizing to one. Documented in
  `test_engine_battery.py`.
- **`Component` schema has no hybrid/on-grid flag**: confirmed by reading `models.py` before writing the
  inverter CSV — a model's hybrid-capability is conveyed only through its model name/manufacturer
  string, matching what `feasibility_engine.py`'s catalog query already assumes (it selects *all*
  inverter-kind components for auto-select, unfiltered by system type).

## Exact import paths for downstream code

```python
from app.engine.report import run_design
from app.engine.types import (
    DesignInputs, ModuleSpec, InverterSpec, Obstruction,
    DesignReport, Flag, Check,
)
from app.engine.battery import UnsupportedSystemType
from app.data.bnef import match_manufacturer
```

`run_design(inputs: DesignInputs) -> DesignReport`; `DesignReport.as_dict()` is the exact ARD §5.3 JSON
shape. All of `app/services/feasibility_engine.py`, `app/agents/tools.py`, `app/routes/components.py`
already import exactly these paths (confirmed by reading them before writing this engine) — no changes
needed on their side now that the modules exist.

---

## Orchestrator decision (2026-08-31) on the string-selection finding above

**Kept `strings.py` unchanged.** "Search downward, prefer the largest passing series count" is the
correct default for a wide-MPPT grid-tie inverter (lower current → less copper, standard EPC practice),
and it's now cross-verified: it exactly reproduces the spec's narrow-window worked example
(124.5V/148.8V/3S×5P/70A) and passes 113/113 tests.

Root cause of the mismatch confirmed: the PRD §6 demo narrative's "3S × 5P" line is the *spec's own
15-panel illustrative example* copy-pasted into a 20-panel demo scenario — an inconsistency that
originated in the source PRD/spec text and was carried into `ARD.md`'s §4.11 table and §5.3 example JSON
when this document was first written. Not a bug in your code.

**Fixed:** `ARD.md` §4.11 and §5.3 now state the actual computed values for the demo case (20 panels,
Longi Hi-MO7 550W, Huawei SUN2000-10KTL-M1): **8S × 3P**, Vmp 332.0V, Voc 396.8V, DC:AC 1.1, BOS fuse
20A, confidence 91, status `pass` with an `ORPHAN_PANELS` warning (4 panels short of a full third
string). `frontend/src/lib/fixtures.ts` updated to match so the frontend isn't built against numbers
the real API will never return.

No code change requested. Thank you for flagging rather than silently picking one — this was exactly
the right call.
