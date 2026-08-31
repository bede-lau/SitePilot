/**
 * Typed fetch wrapper over every endpoint in ARD.md §5.1. Existing exports (`API_BASE`,
 * `formatMYR`, the `api` object's pre-existing methods) are kept working so the current pages
 * keep compiling — new methods are additive.
 */
import { formatMYR as formatMYRImpl } from "./format";
import type {
  AnalyticsOverview,
  BnefCheckResponse,
  ChatMessage,
  ChatSendRequest,
  ChatSendResponse,
  ComponentKind,
  ComponentRow,
  DesignReport,
  FeasibilityRequest,
  InspectionReport,
  InvoiceDraft,
  OverviewResponse,
  PoGenerateRequest,
  PoGenerateResponse,
  Project,
  ProjectDetail,
  PurchaseOrder,
  SupplierQuote,
  UploadResponse,
  Vendor,
  VoiceTranscribeResponse,
} from "./types";

// Use 127.0.0.1, NOT "localhost". On Windows, `localhost` resolves to ::1 (IPv6)
// first; uvicorn binds IPv4 only, so the browser spends its full IPv6 connect
// timeout (~2 min) on the dead ::1 address before falling back to 127.0.0.1 —
// that was the "chat takes 2 minutes" hang (Telegram was unaffected because it
// never touches localhost). Forcing IPv4 here removes the dual-stack race.
export const API_BASE =
  (import.meta as { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE || "http://127.0.0.1:8000";

// Re-exported for backward compatibility — every existing page imports these types from
// "../lib/api" and must keep working unmodified. New code should prefer importing from
// "../lib/types" directly.
export type {
  AnalyticsOverview,
  InspectionReport,
  InvoiceDraft,
  Project,
  ProjectBudget,
  ProjectDetail,
  PurchaseOrder,
  SpendTrendPoint,
  Vendor,
  VendorLeaderboardEntry,
} from "./types";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

async function postBlob(path: string, body: unknown): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.blob();
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") usp.set(key, String(value));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  // ---- existing endpoints (unchanged behavior) ----------------------------
  listProjects: () => getJSON<Project[]>("/projects"),
  getProject: (id: number | string) => getJSON<ProjectDetail>(`/projects/${id}`),
  listInspections: () => getJSON<InspectionReport[]>("/inspections"),
  listInvoices: () => getJSON<InvoiceDraft[]>("/invoices"),
  listPurchaseOrders: () => getJSON<PurchaseOrder[]>("/purchase-orders"),
  listVendors: () => getJSON<Vendor[]>("/vendors"),
  getAnalytics: () => getJSON<AnalyticsOverview>("/analytics/overview"),

  // ---- ARD §5.1 new endpoints ----------------------------------------------
  getOverview: () => getJSON<OverviewResponse>("/api/overview"),

  uploadFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return postForm<UploadResponse>("/api/uploads", form);
  },

  parseQuote: (fileId: string, projectId?: number) =>
    postJSON<SupplierQuote>("/api/quotes/parse", { file_id: fileId, project_id: projectId }),
  listQuotes: () => getJSON<SupplierQuote[]>("/api/quotes"),
  getQuote: (id: number | string) => getJSON<SupplierQuote>(`/api/quotes/${id}`),

  runFeasibility: (request: FeasibilityRequest) => postJSON<DesignReport>("/api/feasibility/run", request),
  getFeasibility: (id: number | string) => getJSON<DesignReport>(`/api/feasibility/${id}`),
  listFeasibilityRuns: (projectId: number) =>
    getJSON<DesignReport[]>(`/api/feasibility${qs({ project_id: projectId })}`),

  listComponents: (params: { kind?: ComponentKind; q?: string; limit?: number } = {}) =>
    getJSON<ComponentRow[]>(`/api/components${qs(params)}`),

  checkBnefTier: (manufacturer: string) =>
    getJSON<BnefCheckResponse>(`/api/bnef/check${qs({ manufacturer })}`),

  generatePO: (request: PoGenerateRequest) => postJSON<PoGenerateResponse>("/api/po/generate", request),

  transcribeVoice: (audio: Blob, filename = "recording.webm") => {
    const form = new FormData();
    form.append("audio", audio, filename);
    return postForm<VoiceTranscribeResponse>("/api/voice/transcribe", form);
  },
  speak: (text: string, voiceId?: string) => postBlob("/api/voice/speak", { text, voice_id: voiceId }),

  getChatHistory: (sessionKey: string) =>
    getJSON<ChatMessage[]>(`/api/chat/history${qs({ session_key: sessionKey })}`),
  sendChat: (request: ChatSendRequest) => postJSON<ChatSendResponse>("/api/chat", request),
};

export const formatMYR = formatMYRImpl;
