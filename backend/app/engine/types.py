"""Typed inputs/outputs for the calculation engine. Spec: whole document; shape: ARD §5.3.

Every dataclass is frozen (immutable) and pure data — no methods that touch I/O, no
``datetime.now()`` defaults. ``DesignReport.as_dict()`` produces exactly the JSON shape
documented in ARD §5.3 (field names, nesting, nulls) so the frontend can render straight
from it. Floats are rounded sensibly *at this boundary only* — never during intermediate
math inside the engine modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Literal


# --------------------------------------------------------------------------- #
# Small shared value types
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Flag:
    """A non-fatal problem surfaced anywhere in the engine. Spec: throughout (⚠ callouts)."""

    level: Literal["info", "warn", "error"]
    code: str
    message: str


@dataclass(frozen=True)
class Check:
    """One row of the UI's evidence table. ARD §4.4 — every validation produces one of these."""

    id: str
    label: str
    expected: str
    actual: float
    unit: str
    passed: bool
    margin_pct: Optional[float] = None


@dataclass(frozen=True)
class Obstruction:
    """Spec §4 Stage 2B roof obstruction. ``kind`` keys into ``constants.OBSTRUCTION_AREA_M2``."""

    kind: str
    count: int = 1


# --------------------------------------------------------------------------- #
# Component specs (resolved concrete values — the engine never looks these up
# itself; the caller resolves a component_id / catalog row into one of these
# before calling run_design()).
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ModuleSpec:
    """PV module electrical spec. Spec §12.5 / ARD §3.3 ``components`` (kind='module')."""

    manufacturer: str
    model: str
    rated_wp: float
    vmp: float
    voc: float
    imp: float
    isc: float
    temp_coeff_voc_pct_per_c: Optional[float] = None
    bnef_tier1: Optional[bool] = None


@dataclass(frozen=True)
class InverterSpec:
    """Inverter electrical spec. ARD §3.3 ``components`` (kind='inverter')."""

    manufacturer: str
    model: str
    ac_rating_kw: float
    max_dc_input_kw: float
    mppt_min_v: float
    mppt_max_v: float
    max_dc_voltage_v: float
    max_input_current_per_mppt_a: float
    mppt_count: int
    phase: Literal["single", "three"] = "single"
    has_anti_islanding: bool = True


# --------------------------------------------------------------------------- #
# Engine input
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class DesignInputs:
    """Everything ``run_design()`` needs. Built by the caller (agents/tools.py) from the
    DB + API request (ARD §5.2 ``FeasibilityRequest``) — the engine itself never touches
    the DB. ``generated_at`` is an ISO-8601 string supplied by the caller (no wall-clock
    reads inside the pure engine).
    """

    generated_at: str
    module: ModuleSpec
    system_type: Literal["on_grid", "hybrid", "off_grid"] = "on_grid"
    project_id: Optional[int] = None
    panel_count: Optional[int] = None
    panel_count_source: Literal["photo", "manual"] = "photo"
    inverter: Optional[InverterSpec] = None
    inverter_catalog: tuple[InverterSpec, ...] = ()
    monthly_consumption_kwh: Optional[float] = None
    state: str = "Selangor"
    roof_area_m2: Optional[float] = None
    roof_tilt_deg: Optional[float] = None
    roof_azimuth_deg: Optional[float] = None
    shading_factor: Optional[float] = None
    obstructions: tuple[Obstruction, ...] = ()
    system_cost_myr: Optional[float] = None
    budget_tier: Literal["entry", "mid", "premium"] = "mid"
    tariff_category: Literal["domestic", "commercial"] = "domestic"
    backup_hours: Optional[float] = None
    critical_appliances: tuple[str, ...] = ()
    has_supplier_quote: bool = False
    dc_ac_ratio_target: float = 1.25


# --------------------------------------------------------------------------- #
# Engine output — mirrors ARD §5.3 DesignReport exactly
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class EfficiencyBreakdown:
    """Spec §4 Stage 2D."""

    base: float
    tilt: float
    azimuth: float
    shading: float
    temperature: float
    effective: float


@dataclass(frozen=True)
class SiteAssessment:
    """Spec §4 Stage 2."""

    state: str
    psh: float
    psh_source: Literal["state_average", "state_default_fallback"]
    roof_area_m2: Optional[float]
    net_area_m2: Optional[float]
    max_panels: Optional[int]
    efficiency: EfficiencyBreakdown


@dataclass(frozen=True)
class LoadProfile:
    """Spec §4/§5 Stage 1."""

    monthly_kwh: Optional[float]
    daily_kwh: Optional[float]
    design_daily_wh: Optional[float]
    safety_factor: float


@dataclass(frozen=True)
class ModuleSummary:
    """Slim module view embedded in ``array``. ARD §5.3."""

    manufacturer: str
    model: str
    rated_wp: float
    vmp: float
    voc: float
    imp: float
    isc: float
    bnef_tier1: Optional[bool]


@dataclass(frozen=True)
class ArraySizing:
    """Spec §5 Stages 1 & 3 / ARD §4.3."""

    panel_count: int
    module: ModuleSummary
    actual_kwp: float
    required_kwp: Optional[float]
    max_roof_kwp: Optional[float]
    constrained: bool
    coverage_pct: Optional[float]
    daily_generation_kwh: Optional[float]
    self_consumed_kwh: Optional[float]
    exported_kwh: Optional[float]
    self_consumption_pct: Optional[float]


@dataclass(frozen=True)
class StringDesign:
    """Spec §4 Stage 6 / ARD §4.4 — the money module."""

    status: Literal["pass", "fail"]
    series: int
    parallel: int
    config_label: str
    panels_used: int
    orphan_panels: int
    vmp_string: float
    voc_string: float
    voc_cold_string: float
    voc_method: Literal["temp_coefficient", "flat_0.85_buffer"]
    total_isc: float
    checks: tuple[Check, ...]


@dataclass(frozen=True)
class InverterSelection:
    """Spec §5 Stage 4 / ARD §4.5."""

    manufacturer: str
    model: str
    ac_rating_kw: float
    max_dc_input_kw: float
    mppt_min_v: float
    mppt_max_v: float
    max_dc_voltage_v: float
    dc_ac_ratio: float
    selected_by: Literal["user", "auto"]
    checks: tuple[Check, ...]


@dataclass(frozen=True)
class BatteryModuleSelection:
    """One row of ``battery.modules`` — ``count`` × ``module_kwh`` LFP packs."""

    count: int
    module_kwh: float
    total_kwh: float


@dataclass(frozen=True)
class BatteryDesign:
    """Spec §6 (hybrid only) / ARD §4.6."""

    critical_load_kw: float
    backup_hours: float
    raw_kwh: float
    final_kwh: float
    ah_at_48v: float
    modules: tuple[BatteryModuleSelection, ...]
    usable_kwh: float
    c_rate: float
    checks: tuple[Check, ...]


@dataclass(frozen=True)
class BosItem:
    """Spec §8 / ARD §4.7."""

    item: str
    spec: str
    rating: str
    standard: str
    note: str


@dataclass(frozen=True)
class BosGroup:
    group: str
    items: tuple[BosItem, ...]


@dataclass(frozen=True)
class BosSpec:
    groups: tuple[BosGroup, ...]


@dataclass(frozen=True)
class BillBreakdown:
    """Spec §12.1 TNB block bill. Internal building block for ``FinancialModel``."""

    kwh: float
    energy_myr: float
    capacity_myr: float
    network_myr: float
    icpt_myr: float
    retail_myr: float
    total_myr: float


@dataclass(frozen=True)
class ProjectionYear:
    year: int
    cumulative_savings: float
    cumulative_net: float


@dataclass(frozen=True)
class FinancialModel:
    """Spec §5 Stage 6, §12.1, §12.3 / ARD §4.8."""

    monthly_generation_kwh: float
    effective_tariff_myr: float
    monthly_savings_myr: float
    annual_savings_myr: float
    bill_before_myr: float
    bill_after_myr: float
    system_cost_myr: float
    cost_range_myr: tuple[float, float]
    payback_years: float
    payback_range_years: tuple[float, float]
    export_kwh: float
    export_rate_myr: float
    rollover: bool
    projection: tuple[ProjectionYear, ...]
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class ConfidenceComponent:
    label: str
    delta: int
    applied: bool
    reason: str


@dataclass(frozen=True)
class ConfidenceSignals:
    """Inputs to ``score_confidence()``. Assembled by report.py from DesignInputs plus
    intermediate results (e.g. whether the string design actually passed). Spec §9 / ARD §4.9.
    """

    supplier_quote_attached: bool
    string_validated_pass: bool
    site_specifics_recorded: bool
    real_consumption_on_record: bool
    manual_panel_count: bool
    psh_is_fallback: bool


@dataclass(frozen=True)
class ConfidenceScore:
    score: int
    band: str
    disclaimer: str
    components: tuple[ConfidenceComponent, ...]


@dataclass(frozen=True)
class DesignReport:
    """The API contract. ARD §5.3 — frontend renders straight from ``as_dict()``."""

    project_id: Optional[int]
    system_type: str
    status: Literal["pass", "warn", "fail"]
    generated_at: str
    confidence: ConfidenceScore
    site: SiteAssessment
    load: LoadProfile
    array: ArraySizing
    strings: StringDesign
    inverter: InverterSelection
    battery: Optional[BatteryDesign]
    bos: BosSpec
    financial: FinancialModel
    equipment_tier: str
    warnings: tuple[Flag, ...]
    assumptions: tuple[str, ...]
    id: Optional[int] = None

    def as_dict(self) -> dict:
        """Exact ARD §5.3 JSON shape. ``dataclasses.asdict`` recurses through every nested
        frozen dataclass and tuple, so this stays correct as long as field names/nesting
        above match the ARD. Tuples become JSON arrays automatically.
        """
        return asdict(self)
