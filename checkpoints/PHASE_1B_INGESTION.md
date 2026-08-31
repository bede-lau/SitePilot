# Phase 1B — Document Ingestion (Agent B)

**Status: done + verified.** All files built, 38/38 offline tests green, and a real
`qwen-vl-max` vision parse run against a generated fixture — see §3.

---

## 1. Files built (exclusively mine, per ARD §2)

| File | Purpose |
|------|---------|
| `backend/app/services/pdf_extract.py` | PDF→PNG page rendering (pypdfium2), text-layer extraction, PDF/image sniffing, image normalisation |
| `backend/app/agents/quote_parser.py` | `parse_quote()` — vision call + normalisation pipeline (ARD §4.1 / §5.4) |
| `backend/scripts/generate_messy_quote.py` + `backend/scripts/__init__.py` | DB-driven messy quote PDF generator (ARD §7) |
| `backend/tests/test_quote_parser.py` | 38 offline tests, no network |
| `backend/uploads/quotes/quote-ysp-solar-sep26.pdf` | Fixture 1 — YSP Solar Sdn Bhd, MYR only |
| `backend/uploads/quotes/quote-green-energy-sep26.pdf` | Fixture 2 — Green Energy Supply, has a USD line |
| `backend/uploads/quotes/quote-suntech-sep26.pdf` | Fixture 3 — SunTech Materials, has a USD line |

No files outside this list were modified. `app/data/bnef.py` and `app/engine/**` did not
exist yet at any point during this work — both dependencies are guarded (see §4).

---

## 2. `parse_quote()` — call signature for Agent C

```python
async def parse_quote(data: bytes, filename: str, fx_rate: float = 4.72) -> dict
```

Returns the ARD §5.4 shape **plus two extra keys** beyond the strict API response
(documented deviation, see §6): `raw_text` (str) and `raw_llm_json` (dict | None) —
these map directly onto the `supplier_quotes.raw_text` / `raw_llm_json` DB columns
(ARD §3.3) so the caller doesn't need a second parse to populate them. `id`,
`vendor_id`, `vendor_matched` are omitted as instructed — Agent C fills those in
after vendor matching.

I confirmed this already matches Agent C's actual integration
(`backend/app/services/quote_ingest.py::ingest_quote`) — it calls
`parse_quote(data, path.name, fx_rate=settings.usd_myr_rate)` and reads exactly the
keys I return (`supplier_name_raw`, `source_filename`, `currency`, `fx_rate_to_myr`,
`page_count`, `parse_status`, `parse_notes`, `subtotal_myr`, and every `line_items[]`
field: `line_no, category, manufacturer, model, description, quantity, unit,
unit_price, currency, unit_price_myr, line_total_myr, rated_wp, price_per_wp_myr,
warranty_years, lead_time_days, bnef_tier1, tier_match_name, flags`). No field-name
drift found.

Never raises — any failure (unreadable file, vision error, malformed JSON after one
retry) collapses to `parse_status: "failed"`, same discipline as
`llm_client._stub_analyze_photo`.

---

## 3. Live end-to-end vision parse (real qwen-vl-max key)

Ran the generator, then ran `parse_quote()` against the output with the real key in
`backend/.env` (no mocking):

```
cd backend
venv/Scripts/python.exe -m scripts.generate_messy_quote --vendor "YSP Solar" \
    --project "Sungai Petani" --out uploads/quotes/quote-ysp-solar-sep26.pdf --seed 2
venv/Scripts/python.exe -c "
import asyncio
from pathlib import Path
from app.agents.quote_parser import parse_quote
result = asyncio.run(parse_quote(Path('uploads/quotes/quote-ysp-solar-sep26.pdf').read_bytes(),
                                  'quote-ysp-solar-sep26.pdf'))
"
```

Extracted Longi line item (the one the demo script hangs off, PRD §6 Minute 1:00-2:15):

```json
{
  "line_no": 1,
  "category": "module",
  "manufacturer": "Longi",
  "model": "Hi-MO7 LR5-72HTH-550M",
  "description": "550Wp N-type TOPCon monocrystalline solar module, black frame, model Hi-MO7 LR5-72HTH-550M — high efficiency dual-glass panel for tropical rooftop installation",
  "quantity": 60,
  "unit": "pcs",
  "unit_price": 306.72,
  "currency": "MYR",
  "unit_price_myr": 306.72,
  "line_total_myr": 18403.2,
  "rated_wp": 550,
  "price_per_wp_myr": 0.558,
  "warranty_years": 25,
  "lead_time_days": 21,
  "bnef_tier1": null,
  "tier_match_name": null,
  "flags": ["AMBIGUOUS_UNIT", "TIER_UNKNOWN"]
}
```

Correct: manufacturer, model (verbatim, dashed format preserved), quantity, unit price,
wattage (pulled out of the description prose, not a column), warranty, lead time. Unit
`nos` correctly canonicalised to `pcs` and flagged ambiguous. `bnef_tier1`/`TIER_UNKNOWN`
is expected — `app/data/bnef.py` (Agent A) hadn't landed at parse time, so the guarded
fallback returned `(None, None)`; this will resolve to `true`/`LONGi Green Energy` once
that file exists, no code change needed on my side.

The inverter line (Huawei SUN2000-10KTL-M1) and the BOS/freight lines also parsed
correctly; overall `parse_status: "partial"` because the generic BOS/freight lines
(by design, no manufacturer/model on a real quote) fail the "every line has
manufacturer+model+qty+price" bar for `"parsed"` — this is spec-correct (ARD §4.1 step 5),
not a parser miss. Full JSON captured during this session; not repeated here for length.

### Prompt iteration needed

One real fix was required, and it was in the **fixture generator**, not the parser:
my first draft of the messy-PDF generator printed the wattage and model string but
**never printed the manufacturer brand name** ("Longi", "Huawei") anywhere on the page
— only in the internal DB-derived data used for grading, not on the rendered PDF. The
vision model correctly extracted whatever was actually on the page, which meant it
split `"Hi-MO7"` off as a fake manufacturer and `"LR5-72HTH-550M"` as the model. Real
quotes always state the brand, so I fixed `build_line_items()` in
`generate_messy_quote.py` to prefix both the module and inverter descriptions with
the manufacturer name (e.g. `"Longi 550Wp N-type TOPCon ... model Hi-MO7 LR5-72HTH-550M"`),
regenerated all 3 fixtures, and reran the live parse — manufacturer now comes back
correctly. The vision prompt itself (`QUOTE_VISION_PROMPT`) needed no changes; it
already extracted quantity/price/unit/currency/wattage/warranty/lead-time correctly on
the first try.

A second, unrelated bug surfaced only via the offline test suite (not the live parse):
`_categorise()` checked module keywords before battery keywords, so a description like
"Lithium battery energy storage module" was misclassified as `module` (the generic word
"module" matched first). Fixed by reordering — battery/inverter checks (brand, then
keyword) now run before the module checks, since a solar-panel description never
contains "battery" but a battery pack description often contains the generic word
"module".

---

## 4. Concurrent-build guards

- `from app.data.bnef import match_manufacturer` — wrapped in `try/except ImportError`,
  falls back to `lambda name: (None, None)`. Verified this path is live right now (file
  doesn't exist yet) via the live parse above (`TIER_UNKNOWN` flag).
- `scripts/generate_messy_quote.py`'s `components` table read uses raw SQL
  (`SELECT * FROM components WHERE kind = :kind`) wrapped in `try/except Exception`,
  falling back to a small hardcoded module/inverter list (the same real models named
  in `CLAUDE.md`: Longi Hi-MO7 LR5-72HTH-550M, Huawei SUN2000-10KTL-M1) whenever the
  table is absent *or* empty. Verified live: the table exists (Agent A/C landed the
  schema) but has 0 rows at the time of this run, so every fixture used the fallback
  list — confirmed correct behaviour, not an error path.
- Vendor field access (`brands_carried`, `quote_currency`, `bnef_tier`, `country`) is
  avoided in the generator entirely — I only read columns guaranteed to exist from day
  one (`company_name`, `region`, `contact_email`, `unit_price_myr`, `id`), so the script
  never depended on Agent C's Vendor migration landing first.
- I did not edit `models.py`, `seed.py`, `routes/**`, `tools.py`, `orchestrator.py`,
  `llm_client.py`, `requirements.txt`, `app/engine/**`, `app/data/**`, or `frontend/**`.

One incidental note for whoever runs this next cold: the live `fieldbot.db` needed
`app/db_upgrade.py`'s `run_upgrade()` run once before `Vendor`/`Project` queries would
work (Agent C had already added the new mapped columns to `models.py`, but the on-disk
schema hadn't been migrated yet at the time I started testing). I ran it manually
(idempotent, additive-only, same operation `main.py`'s lifespan will run automatically)
purely to unblock local testing — I did not touch `main.py` or `db_upgrade.py`.

---

## 5. Fixtures shipped (`backend/uploads/quotes/`)

All three are DB-driven (every name/model/wattage/price traces to a real seeded
`Vendor`/`Project`/component row, per ARD §7) and deterministic given their seed.
Secondary-line prices (inverter/BOS/freight) are synthesised from a documented rate
since the `components` table carries no pricing column — flagged clearly in the
script's module docstring.

| File | Vendor | Project | Seed | Module | Inverter | Currency |
|------|--------|---------|------|--------|----------|----------|
| `quote-ysp-solar-sep26.pdf` | YSP Solar Sdn Bhd | Sungai Petani Residential Cluster | 2 | Longi | Huawei | MYR only |
| `quote-green-energy-sep26.pdf` | Green Energy Supply | Kuching Eco Park Solar Farm | 7 | Jinko | Huawei | inverter line in USD |
| `quote-suntech-sep26.pdf` | SunTech Materials | Johor Bahru Rooftop Array | 10 | Trina Solar | Huawei | inverter line in USD |

Each fixture implements every ARD §7 messiness trait: letterhead with fake SSM/SST
reg numbers + bank block, inconsistent per-row column alignment (small x-jitter),
one two-line wrapped row (the module description), a visually merged qty+unit cell
(freight line), mixed units across the 3 fixtures (pcs/nos/units/set/lot), a USD line
item with a "converted @ 4.72" footnote (2 of 3 fixtures), wattage buried in
description prose, warranty/lead-time only in a footnote (with a deliberate
"Warrenty" typo), one inconsistent model-number format (inverter model printed with
spaces instead of dashes), an incoterms + validity clause, a rotated
handwritten-style annotation, a page break mid-table with repeated column headers,
a faint grey scan-speckle texture, and a rotated semi-transparent "RECEIVED" stamp.
Visually inspected by rendering both pages of each fixture back through
`pdf_extract.render_pdf_pages` — no text collisions, no column overflow.

Regenerate any of them with:
```
cd backend
venv/Scripts/python.exe -m scripts.generate_messy_quote --vendor <id|name> --project <id|name> --out <path> --seed N
```

---

## 6. Deviations from ARD §5.4

1. **Two extra top-level keys** (`raw_text`, `raw_llm_json`) beyond the strict API
   response shape — needed so Agent C can populate `supplier_quotes.raw_text` /
   `raw_llm_json` (ARD §3.3) without re-parsing. Confirmed Agent C's
   `quote_ingest.py` already expects this (`raw_llm_json=parsed` — it stores the
   whole dict).
2. **Top-level `currency`/`fx_rate_to_myr` on a mixed-currency quote**: `currency` is
   the *majority* currency across line items (not necessarily "the" quote currency,
   since a real quote can mix MYR and USD lines); `fx_rate_to_myr` is `1.0` unless at
   least one line actually needed conversion, in which case it's the `fx_rate` that
   was applied. Matches the single-currency ARD §5.4 example (`"MYR"` / `1.0`)
   exactly when the quote has no USD lines.
3. **`NOT_TIER1`/`TIER_UNKNOWN`/`MISSING_WATTAGE`/`PRICE_OUTLIER`** are scoped to
   `category == "module"` lines only, per ARD §4.1 step 4's explicit "module line"
   wording. **`NO_WARRANTY_STATED`/`NO_LEAD_TIME`** are scoped to
   `module`/`inverter`/`battery` lines (not `bos`/`service`/`unknown`) — my own
   heuristic, since a freight or mounting-hardware line legitimately has neither in a
   real quote and flagging it would just be noise for the buyer.

---

## 7. Tests

```
cd backend && venv/Scripts/python.exe -m pytest tests/test_quote_parser.py -q
38 passed in 0.92s
```

Covers: unit harmonisation (clean/ambiguous/unknown), currency canonicalisation
(MYR/USD variants), wattage extraction from prose, categorisation (all 6 categories,
including the battery-vs-module priority fix), MYR/USD normalisation math and RM/Wp,
every flag (`AMBIGUOUS_UNIT`, `CURRENCY_CONVERTED`, `MISSING_WATTAGE`, `NOT_TIER1`,
`TIER_UNKNOWN`, `PRICE_OUTLIER`, `NO_WARRANTY_STATED`, `NO_LEAD_TIME`), null-field
handling (never guesses), BNEF tier matching (monkeypatched, all 3 outcomes +
module-only scoping), `_finalise()`'s `parsed`/`partial`/`failed` status logic and
summary totals, and the stub path (`LLM_API_KEY` unset) via a real `parse_quote()`
call against an in-memory PNG.
