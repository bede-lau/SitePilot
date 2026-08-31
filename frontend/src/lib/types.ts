/**
 * Hand-written TypeScript types for the SitePilot API contract.
 * Source of truth: ARD.md §3 (data model), §5.1-§5.6 (API contract).
 *
 * Frontend rule (ARD §5.3): never recompute a number from a payload — render what is there.
 * If a field is missing, show an em-dash, not a guess.
 */

// ---------------------------------------------------------------------------
// §3 — existing entities, extended additively with the new columns
// ---------------------------------------------------------------------------

export type SystemType = "on_grid" | "hybrid";
export type TariffCategory = "domestic" | "commercial";

export interface Obstruction {
  kind: "water_tank" | "aircon_compressor" | "solar_water_heater" | string;
  count: number;
}

export interface Project {
  id: number;
  name: string;
  client_name: string;
  site_location: string;
  region: string;
  phase: string | null;
  total_panels: number;
  contract_value: number;
  status: string;
  created_at: string;
  // §3.1 additive columns — optional until the platform agent lands db_upgrade.py
  state?: string;
  system_type?: SystemType;
  monthly_consumption_kwh?: number | null;
  tariff_category?: TariffCategory;
  roof_area_m2?: number | null;
  roof_tilt_deg?: number | null;
  roof_azimuth_deg?: number | null;
  shading_factor?: number | null;
  obstructions?: Obstruction[];
}

export interface ProjectDetail extends Project {
  inspections_count: number;
  invoices_count: number;
  purchase_orders_count: number;
}

export interface InspectionReport {
  id: number;
  project_id: number;
  submitted_by_phone: string | null;
  photo_urls: string[];
  panels_detected: number | null;
  panels_with_issues: number;
  issues: string[];
  completion_pct: number | null;
  created_at: string;
}

export interface InvoiceDraft {
  id: number;
  project_id: number;
  inspection_report_id: number | null;
  invoice_number: string;
  claim_percentage: number | null;
  claim_amount_myr: number | null;
  status: string;
  created_at: string;
}

export interface PurchaseOrder {
  id: number;
  project_id: number;
  vendor_id: number;
  po_number: string;
  item_description: string;
  quantity: number;
  unit_price_myr: number | null;
  total_price_myr: number | null;
  status: string;
  created_at: string;
}

export interface Vendor {
  id: number;
  company_name: string;
  region: string;
  contact_email: string;
  on_time_rate: number | null;
  unit_price_myr: number | null;
  specialization: string | null;
  is_active: boolean;
  created_at: string;
  // §3.2 additive columns
  bnef_tier?: number | null;
  brands_carried?: string[];
  country?: string;
  quote_currency?: string;
}

export interface ProjectBudget {
  project_id: number;
  name: string;
  region: string;
  status: string;
  contract_value: number;
  spend: number;
  budget_used_pct: number;
  completion_pct: number;
}

export interface VendorLeaderboardEntry {
  vendor_id: number;
  company_name: string;
  region: string;
  specialization: string | null;
  on_time_rate: number;
  total_orders: number;
  total_spend: number;
}

export interface SpendTrendPoint {
  month: string;
  amount: number;
}

export interface AnalyticsOverview {
  total_contract_value: number;
  total_spend: number;
  active_projects: number;
  completed_projects: number;
  total_panels_with_issues: number;
  project_budgets: ProjectBudget[];
  vendor_leaderboard: VendorLeaderboardEntry[];
  spend_trend: SpendTrendPoint[];
  generated_at: string;
}

// ---------------------------------------------------------------------------
// §3.3 — components catalog
// ---------------------------------------------------------------------------

export type ComponentKind = "module" | "inverter";
export type ComponentSource = "CEC" | "manufacturer" | "parsed_quote";

export interface ComponentRow {
  id: number;
  kind: ComponentKind;
  manufacturer: string;
  model: string;
  tier: number | null;
  // module fields
  rated_wp?: number | null;
  vmp?: number | null;
  voc?: number | null;
  imp?: number | null;
  isc?: number | null;
  temp_coeff_voc_pct_per_c?: number | null;
  efficiency_pct?: number | null;
  cell_tech?: string | null;
  area_m2?: number | null;
  // inverter fields
  ac_rating_kw?: number | null;
  max_dc_input_kw?: number | null;
  mppt_min_v?: number | null;
  mppt_max_v?: number | null;
  max_dc_voltage_v?: number | null;
  max_input_current_per_mppt_a?: number | null;
  mppt_count?: number | null;
  phase?: "single" | "three" | null;
  euro_efficiency_pct?: number | null;
  has_anti_islanding?: boolean | null;
  // shared
  datasheet_url?: string | null;
  source: ComponentSource;
  created_at: string;
}

// ---------------------------------------------------------------------------
// §5.2 — FeasibilityRequest
// ---------------------------------------------------------------------------

export type BudgetTier = "entry" | "mid" | "premium";

export interface ComponentRef {
  component_id: number;
}

export interface InlineModuleSpec {
  manufacturer: string;
  model: string;
  rated_wp: number;
  vmp: number;
  voc: number;
  imp: number;
  isc: number;
}

export interface InlineInverterSpec {
  manufacturer: string;
  model: string;
  ac_rating_kw: number;
  max_dc_input_kw: number;
  mppt_min_v: number;
  mppt_max_v: number;
  max_dc_voltage_v: number;
  max_input_current_per_mppt_a: number;
  mppt_count: number;
}

export interface FeasibilityRequest {
  project_id: number;
  system_type: SystemType;
  panel_count?: number;
  module?: ComponentRef | InlineModuleSpec;
  inverter?: ComponentRef | InlineInverterSpec;
  quote_id?: number;
  monthly_consumption_kwh?: number;
  system_cost_myr?: number;
  budget_tier?: BudgetTier;
  backup_hours?: number;
  critical_appliances?: string[];
}

// ---------------------------------------------------------------------------
// §5.3 — DesignReport: the shape everything renders from
// ---------------------------------------------------------------------------

export type RunStatus = "pass" | "warn" | "fail";
export type ConfidenceBand =
  | "Indicative"
  | "Good estimate"
  | "Solid — suitable for quotation"
  | "Detailed specification — installer to confirm string design";

export interface ConfidenceComponent {
  label: string;
  delta: number;
  applied: boolean;
  reason: string;
}

export interface ConfidenceScore {
  score: number;
  band: ConfidenceBand | string;
  disclaimer: string;
  components: ConfidenceComponent[];
}

export interface EfficiencyBreakdown {
  base: number;
  tilt: number;
  azimuth: number;
  shading: number;
  temperature: number;
  effective: number;
}

export type PshSource = "state_average" | "site_specific";

export interface SiteAnalysis {
  state: string;
  psh: number;
  psh_source: PshSource | string;
  roof_area_m2: number | null;
  net_area_m2: number | null;
  max_panels: number | null;
  efficiency: EfficiencyBreakdown;
}

export interface LoadAnalysis {
  monthly_kwh: number | null;
  daily_kwh: number | null;
  design_daily_wh: number | null;
  safety_factor: number;
}

export interface ArrayModule {
  manufacturer: string;
  model: string;
  rated_wp: number;
  vmp: number;
  voc: number;
  imp: number;
  isc: number;
  bnef_tier1: boolean | null;
}

export interface ArrayDesign {
  panel_count: number;
  module: ArrayModule;
  actual_kwp: number;
  required_kwp: number | null;
  max_roof_kwp: number | null;
  constrained: boolean;
  coverage_pct: number | null;
  daily_generation_kwh: number;
  self_consumed_kwh: number;
  exported_kwh: number;
  self_consumption_pct: number;
}

export interface Check {
  id: string;
  label: string;
  expected: string;
  actual: number | string;
  unit: string;
  passed: boolean;
  margin_pct: number | null;
}

export type VocMethod = "temp_coefficient" | "flat_0.85_buffer";

export interface StringDesign {
  series: number;
  parallel: number;
  config_label: string;
  panels_used: number;
  orphan_panels: number;
  vmp_string: number;
  voc_string: number;
  voc_cold_string: number;
  voc_method: VocMethod | string;
  total_isc: number;
  checks: Check[];
  status?: RunStatus;
}

export type SelectedBy = "auto" | "user";

export interface InverterDesign {
  manufacturer: string;
  model: string;
  ac_rating_kw: number;
  max_dc_input_kw: number;
  mppt_min_v: number;
  mppt_max_v: number;
  max_dc_voltage_v: number;
  dc_ac_ratio: number;
  selected_by: SelectedBy;
  checks: Check[];
}

export interface BatteryModuleCount {
  count: number;
  module_kwh: number;
}

export interface BatteryDesign {
  raw_kwh: number;
  final_kwh: number;
  ah_at_48v: number;
  modules: BatteryModuleCount[];
  c_rate: number;
  checks: Check[];
}

export interface BosItem {
  item: string;
  spec: string;
  rating: string;
  standard: "IEC 62548" | "IEC 60364" | "TNB TCG" | "MS IEC 60947" | string;
  note: string;
}

export interface BosGroup {
  group: string;
  items: BosItem[];
}

export interface BosSpec {
  groups: BosGroup[];
}

export interface FinancialProjectionPoint {
  year: number;
  cumulative_savings: number;
  cumulative_net: number;
}

export interface FinancialModel {
  monthly_generation_kwh: number;
  effective_tariff_myr: number;
  monthly_savings_myr: number;
  annual_savings_myr: number;
  bill_before_myr: number;
  bill_after_myr: number;
  system_cost_myr: number;
  cost_range_myr: [number, number];
  payback_years: number;
  payback_range_years: [number, number];
  export_kwh: number;
  export_rate_myr: number;
  rollover: boolean;
  projection: FinancialProjectionPoint[];
  assumptions: string[];
}

export type FlagLevel = "info" | "warn" | "error";

export interface Flag {
  level: FlagLevel;
  code: string;
  message: string;
}

export interface DesignReport {
  id: number;
  project_id: number;
  system_type: SystemType;
  status: RunStatus;
  generated_at: string;
  confidence: ConfidenceScore;
  site: SiteAnalysis;
  load: LoadAnalysis;
  array: ArrayDesign;
  strings: StringDesign;
  inverter: InverterDesign;
  battery: BatteryDesign | null;
  bos: BosSpec;
  financial: FinancialModel;
  equipment_tier: BudgetTier | string;
  warnings: Flag[];
  assumptions: string[];
}

// ---------------------------------------------------------------------------
// §5.4 — SupplierQuote
// ---------------------------------------------------------------------------

export type ParseStatus = "parsed" | "partial" | "failed";
export type LineItemCategory = "module" | "inverter" | "battery" | "bos" | "service" | "unknown";

export interface QuoteLineItem {
  line_no: number;
  category: LineItemCategory;
  manufacturer: string | null;
  model: string | null;
  description: string;
  quantity: number;
  unit: string;
  unit_price: number;
  currency: string;
  unit_price_myr: number;
  line_total_myr: number;
  rated_wp: number | null;
  price_per_wp_myr: number | null;
  warranty_years: number | null;
  lead_time_days: number | null;
  bnef_tier1: boolean | null;
  tier_match_name: string | null;
  flags: string[];
}

export interface QuoteSummary {
  total_wp: number;
  blended_price_per_wp_myr: number;
  tier1_line_count: number;
  flagged_line_count: number;
}

export interface SupplierQuote {
  id: number;
  supplier_name_raw: string;
  vendor_id: number | null;
  vendor_matched: boolean;
  source_filename: string;
  currency: string;
  fx_rate_to_myr: number;
  parse_status: ParseStatus;
  page_count: number;
  subtotal_myr: number;
  parse_notes: string;
  line_items: QuoteLineItem[];
  summary: QuoteSummary;
}

// ---------------------------------------------------------------------------
// §5.1 — misc REST payloads
// ---------------------------------------------------------------------------

export interface OverviewTrendPoint {
  month: string;
  value: number;
}

export interface OverviewResponse {
  total_capacity_kwp: number;
  active_projects: number;
  open_rfqs: number;
  po_value_myr: number;
  avg_confidence: number;
  panels_installed: number;
  co2_avoided_tonnes: number;
  generation_trend: OverviewTrendPoint[];
  spend_trend: OverviewTrendPoint[];
}

export type UploadKind = "pdf" | "image" | "audio";

export interface UploadResponse {
  file_id: string;
  filename: string;
  url: string;
  kind: UploadKind;
  size: number;
}

export interface BnefCheckResponse {
  manufacturer: string;
  tier1: boolean;
  matched_name: string | null;
  source: string;
}

export interface PoGenerateRequest {
  feasibility_run_id: number;
  vendor_id?: number;
  notify_telegram: boolean;
}

export interface PoGenerateResponse {
  po: PurchaseOrder;
  pdf_url: string;
  telegram_sent: boolean;
}

export interface VoiceTranscribeResponse {
  text: string;
  duration_s: number;
  language: string;
}

export type ChatRole = "user" | "assistant" | "system";

export interface ChatCard {
  card_type: CardType;
  data: unknown;
}

export interface ChatMessage {
  id: number;
  session_key: string;
  role: ChatRole;
  content: string;
  cards: ChatCard[];
  attachments: UploadResponse[];
  tool_trace: unknown[];
  created_at: string;
}

export interface ChatSendRequest {
  session_key: string;
  message: string;
  attachments?: UploadResponse[];
}

export interface ChatSendResponse {
  reply: string;
  cards: ChatCard[];
}

// ---------------------------------------------------------------------------
// §5.5 — SSE event protocol for POST /api/chat/stream
// ---------------------------------------------------------------------------

export type CardType =
  | "quote_parsed"
  | "feasibility"
  | "bos_spec"
  | "financial"
  | "confidence"
  | "po_draft"
  | "project_summary"
  | "vendor_list"
  | "rfq_status"
  | "component_pick";

export interface StatusEventPayload {
  label: string;
  phase: string;
}

export interface ToolEventPayload {
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResultEventPayload {
  name: string;
  ok: boolean;
  summary: string;
  ms: number;
}

export interface DeltaEventPayload {
  text: string;
}

export interface CardEventPayload {
  card_type: CardType;
  data: unknown;
}

export interface WarningEventPayload {
  level: FlagLevel;
  message: string;
}

export interface DoneEventPayload {
  message_id: number;
  cards: ChatCard[];
}

export interface ErrorEventPayload {
  message: string;
}

export type ChatStreamEvent =
  | { type: "status"; data: StatusEventPayload }
  | { type: "tool"; data: ToolEventPayload }
  | { type: "tool_result"; data: ToolResultEventPayload }
  | { type: "delta"; data: DeltaEventPayload }
  | { type: "card"; data: CardEventPayload }
  | { type: "warning"; data: WarningEventPayload }
  | { type: "done"; data: DoneEventPayload }
  | { type: "error"; data: ErrorEventPayload };
