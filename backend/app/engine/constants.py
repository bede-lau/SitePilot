"""Fixed engineering + Malaysia market constants. Spec §3, §7, §12.

Every value here traces to a spec table cell. Nothing in this module is user-editable at
runtime except via the documented env var overrides (``USD_MYR_RATE``). No I/O.
"""
from __future__ import annotations

import os

# --------------------------------------------------------------------------- #
# §3.1 — fixed engineering constants
# --------------------------------------------------------------------------- #

BASE_EFFICIENCY = 0.75
SAFETY_FACTOR_LOAD = 1.20
TEMP_DERATING = 0.85
SIZING_MARGIN = 1.10
DEFAULT_PANEL_WP = 550
PANEL_FOOTPRINT_M2 = 2.1
LIFEPO4_DOD = 0.80
SYSTEM_VOLTAGE_DC = 48
COLD_VOC_BUFFER = 0.85
COLD_TEMP_C = 20  # T_cold used for the coefficient-based Voc cold adjustment (ARD §4.4)

DCAC_RATIO_MIN = 1.2
DCAC_RATIO_MAX = 1.5
DCAC_RATIO_DEFAULT = 1.25

# Roof-assessment defaults applied when a Project column is null (ARD §3.1).
DEFAULT_ROOF_TILT_DEG = 15.0
DEFAULT_ROOF_AZIMUTH_DEG = 0.0
DEFAULT_SHADING_FACTOR = 0.95

# §6 hybrid battery
BATTERY_SAFETY_MARGIN_HYBRID = 1.10
BATTERY_SAFETY_MARGIN_OFFGRID = 1.12
BATTERY_MAX_C_RATE = 0.80  # spec §4 Stage 4D / §6 Stage 5B — increase battery until <= 0.8C

# --------------------------------------------------------------------------- #
# §3.2 — Peak Sun Hours by state. (low, high) hrs/day; helper below returns the midpoint.
# --------------------------------------------------------------------------- #

PSH_BY_STATE: dict[str, tuple[float, float]] = {
    "Perlis": (4.6, 5.0),
    "Kedah": (4.6, 5.0),
    "Penang": (4.2, 4.5),
    "Pulau Pinang": (4.2, 4.5),
    "Perak": (4.3, 4.6),
    "Selangor": (4.2, 4.5),
    "Kuala Lumpur": (4.2, 4.5),
    "KL": (4.2, 4.5),
    "Negeri Sembilan": (4.3, 4.6),
    "Melaka": (4.4, 4.7),
    "Malacca": (4.4, 4.7),
    "Johor": (4.4, 4.8),
    "Pahang": (4.0, 4.4),
    "Kelantan": (3.8, 4.2),
    "Terengganu": (3.8, 4.2),
    "Sabah": (3.8, 4.3),
    "Sarawak": (3.5, 4.0),
}

DEFAULT_PSH_STATE = "Selangor"


def psh_for_state(state: str | None) -> tuple[float, bool]:
    """Spec §3.2. Returns (midpoint PSH, is_fallback).

    ``is_fallback`` is True only when ``state`` is not a recognised key (so we silently
    default to Selangor's figure) — matching the confidence model's "PSH fallback" signal
    (ARD §4.9), which penalises *not knowing the state at all*, not the ordinary use of a
    state-average PSH (this product has no per-address irradiance API — see PRD §3 EXCLUDE
    of the Google Solar API — so a state average is the normal path, not a degraded one).
    """
    if state:
        key = state.strip()
        for name, (low, high) in PSH_BY_STATE.items():
            if name.lower() == key.lower():
                return round((low + high) / 2, 2), False
    low, high = PSH_BY_STATE[DEFAULT_PSH_STATE]
    return round((low + high) / 2, 2), True


# --------------------------------------------------------------------------- #
# Spec §4 Stage 2D — tilt / azimuth factor bands
# --------------------------------------------------------------------------- #

# (upper_bound_deg_inclusive, factor) — first band whose upper bound the tilt falls under wins.
TILT_FACTORS: tuple[tuple[float, float], ...] = (
    (9, 0.95),
    (15, 1.00),
    (25, 0.97),
    (float("inf"), 0.90),
)

# (upper_bound_deg_inclusive, factor) for degrees-from-south (0 = true south).
AZIMUTH_FACTORS: tuple[tuple[float, float], ...] = (
    (0, 1.00),
    (22.5, 0.98),
    (45, 0.93),
    (67.5, 0.85),
    (90, 0.75),
)
# Beyond 90 deg from south the spec only says "FLAG — suboptimal, warn user" with no
# numeric factor; we hold at the worst tabulated value (0.75) and rely on the WARN flag
# (site.azimuth_flag) to tell the user the orientation itself is the problem.
AZIMUTH_FACTOR_BEYOND_90 = 0.75

OBSTRUCTION_AREA_M2: dict[str, float] = {
    "water_tank": 2.0,
    "aircon_compressor": 1.0,
    "solar_water_heater": 4.0,
}

# --------------------------------------------------------------------------- #
# §12.1 / §3.3 — TNB tariff reference (2026), Tariff A Domestic
# --------------------------------------------------------------------------- #

# (block_upper_kwh, rate_sen_per_kwh) — cumulative blocks, last band is unbounded.
TNB_BLOCKS_DOMESTIC: tuple[tuple[float, float], ...] = (
    (200, 21.80),
    (300, 33.40),
    (600, 51.60),
    (900, 54.60),
    (float("inf"), 57.10),
)

CAPACITY_CHARGE_SEN = 4.55
NETWORK_CHARGE_SEN = 12.85
ICPT_SEN = 3.70
RETAIL_CHARGE_MYR = 10.0
RETAIL_CHARGE_WAIVER_KWH = 600

# Commercial tariff has no published block table in the spec; §3.3 gives flat generation
# bands instead (used for the tariff sanity cross-check, and as the commercial energy rate
# here since no block schedule was provided — see financial.py docstring for detail).
TNB_RP4_GEN_SEN_LOW = 27.03  # <= 1500 kWh/month
TNB_RP4_GEN_SEN_HIGH = 37.03  # > 1500 kWh/month
TNB_RP4_COMMERCIAL_THRESHOLD_KWH = 1500

ATAP_SMP_MYR = 0.18
ATAP_DOMESTIC_RETAIL_RANGE = (0.27, 0.37)
EXPORT_ROLLOVER = False  # spec §3.3 / §5 — credits do not roll over between billing months

# --------------------------------------------------------------------------- #
# Financial projection assumptions (ARD §4.8 — not from the spec, must be documented
# in every FinancialModel's assumptions list).
# --------------------------------------------------------------------------- #

MODULE_DEGRADATION_PCT_PER_YEAR = 0.5
TARIFF_ESCALATION_PCT_PER_YEAR = 3.0
PROJECTION_YEARS = 25

# --------------------------------------------------------------------------- #
# Spec §5 Stage 4 / §6 Stage 6 — standard catalogue sizes
# --------------------------------------------------------------------------- #

STANDARD_GRIDTIE_KW: tuple[float, ...] = (3, 4, 5, 6, 8, 10, 12, 15)
STANDARD_HYBRID_KW: tuple[float, ...] = (3.6, 5, 6, 8, 10, 12)

LFP_MODULES_KWH: tuple[float, ...] = (5.12, 10.24, 15.36)

# --------------------------------------------------------------------------- #
# §12.5 — default/reference 550W panel (used when Tier 2 generic / no model specified)
# --------------------------------------------------------------------------- #

DEFAULT_MODULE_550W = {
    "manufacturer": "Generic",
    "model": "Standard 550W Reference Module",
    "rated_wp": 550.0,
    "vmp": 41.5,
    "voc": 49.6,
    "imp": 13.2,
    "isc": 14.0,
    # Left null intentionally: the spec (§12.5) only tabulates a Pmax temperature
    # coefficient (-0.35%/°C), not a Voc-specific one, for this generic reference panel.
    # With no coefficient available, strings.py falls back to the flat 0.85 cold-buffer
    # method — the same method the PRD §6 demo narrative assumes (Voc_cold == Voc_string
    # == 148.8 V for 3S). See engine/strings.py docstring.
    "temp_coeff_voc_pct_per_c": None,
}

# --------------------------------------------------------------------------- #
# §7 — equipment selection by budget tier
# --------------------------------------------------------------------------- #

COST_RANGES_MYR: dict[tuple[str, str], tuple[float, float]] = {
    # (system_type, tier) -> (low, high), spec §7 "Cost Ranges (Malaysia 2026 market)"
    ("on_grid", "entry"): (15000, 22000),
    ("on_grid", "mid"): (22000, 35000),
    ("on_grid", "premium"): (35000, 50000),
    ("off_grid", "entry"): (40000, 55000),
    ("off_grid", "mid"): (55000, 75000),
    ("off_grid", "premium"): (75000, 100000),
    ("hybrid", "entry"): (28000, 38000),
    ("hybrid", "mid"): (38000, 55000),
    ("hybrid", "premium"): (55000, 75000),
}

EQUIPMENT_BY_TIER: dict[str, dict[str, tuple[str, ...]]] = {
    "panel": {
        "entry": ("Risen", "Canadian Solar", "JA Solar"),
        "mid": ("Longi", "Trina", "JA Solar"),
        "premium": ("Longi Hi-MO7", "Trina Vertex N"),
    },
    "inverter_on_grid": {
        "entry": ("Growatt MIN", "Solis"),
        "mid": ("Solis", "Huawei SUN2000"),
        "premium": ("SMA", "Fronius", "SolarEdge"),
    },
    "inverter_hybrid": {
        "entry": ("Growatt SPH",),
        "mid": ("Deye", "Solis RHI"),
        "premium": ("SMA Sunny Tripower", "Victron"),
    },
    "battery": {
        "entry": ("Entry LFP", "Generic 48V"),
        "mid": ("Pylontech US5000", "Dyness B4850", "BYD Battery-Box Premium LVS"),
        "premium": ("Pylontech Force H2", "CATL"),
    },
}

# --------------------------------------------------------------------------- #
# §2.4 (referenced by ARD §4.1) — hybrid critical-appliance wattages
# --------------------------------------------------------------------------- #

CRITICAL_APPLIANCE_W: dict[str, float] = {
    "refrigerator": 150,
    "lights": 100,
    "wifi_router": 20,
    "fans": 150,
    "aircon_1_unit": 1500,
    "aircon_2_units": 3000,
    "water_pump": 750,
}

# Backup hours by outage frequency (spec §6 Stage 4B) — offered for callers that collect
# an outage-frequency answer instead of an hours value directly.
BACKUP_HOURS_BY_FREQUENCY: dict[str, float] = {
    "rarely": 4,
    "sometimes": 6,
    "frequently": 10,
}

# --------------------------------------------------------------------------- #
# §8 — BOS standard sizes / ampacity tables
# --------------------------------------------------------------------------- #

DC_FUSE_STANDARD_A: tuple[float, ...] = (10, 12, 15, 16, 20, 25, 30)
DC_ISOLATOR_STANDARD_V: tuple[float, ...] = (600, 800, 1000, 1100, 1500)
AC_MCB_STANDARD_A: tuple[float, ...] = (16, 20, 25, 32, 40, 50, 63, 80, 100)

# (cross_section_mm2, ampacity_a)
CABLE_AMPACITY: tuple[tuple[float, float], ...] = (
    (4, 32),
    (6, 41),
    (10, 57),
    (16, 76),
    (25, 101),
    (35, 125),
    (50, 151),
    (70, 192),
    (95, 232),
)

DC_STRING_CABLE_MM2 = 4  # standard for runs <=15m, <20A (spec §8)
DC_BATTERY_CABLE_MM2 = 50  # standard for 150A at <=2m (spec §8, hybrid only)
DC_ISOLATOR_MARGIN = 1.2  # rated for system voltage + 20%
DC_FUSE_MARGIN = 1.25  # 1.25 x Isc per string
AC_CURRENT_MARGIN = 1.25  # cable ampacity picked >= I_ac x 1.25
VOLTAGE_DROP_BUDGET_PCT = 1.5
EARTH_ROD_MIN_DIAMETER_MM = 16
EARTH_ROD_LENGTH_M = 2.4
EARTH_RESISTANCE_MAX_OHM = 5

AC_VOLTAGE_SINGLE_PHASE = 230
AC_VOLTAGE_THREE_PHASE = 415
AC_POWER_FACTOR = 0.95

# --------------------------------------------------------------------------- #
# FX
# --------------------------------------------------------------------------- #

USD_MYR_RATE = float(os.environ.get("USD_MYR_RATE", "4.72"))
