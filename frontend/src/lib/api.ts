export const API_BASE = "http://localhost:8000";

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

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export const api = {
  listProjects: () => getJSON<Project[]>("/projects"),
  getProject: (id: number | string) => getJSON<ProjectDetail>(`/projects/${id}`),
  listInspections: () => getJSON<InspectionReport[]>("/inspections"),
  listInvoices: () => getJSON<InvoiceDraft[]>("/invoices"),
  listPurchaseOrders: () => getJSON<PurchaseOrder[]>("/purchase-orders"),
  listVendors: () => getJSON<Vendor[]>("/vendors"),
  getAnalytics: () => getJSON<AnalyticsOverview>("/analytics/overview"),
};

export function formatMYR(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "RM 0";
  return `RM ${Math.round(amount).toLocaleString("en-MY")}`;
}
