import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ProgressBar from "../components/ProgressBar";
import {
  api,
  formatMYR,
  type AnalyticsOverview,
  type InspectionReport,
  type InvoiceDraft,
  type ProjectDetail as ProjectDetailType,
  type PurchaseOrder,
  type Vendor,
} from "../lib/api";

type Tab = "inspections" | "invoices" | "pos";

export default function ProjectDetail() {
  const { id } = useParams();
  const [project, setProject] = useState<ProjectDetailType | null>(null);
  const [inspections, setInspections] = useState<InspectionReport[]>([]);
  const [invoices, setInvoices] = useState<InvoiceDraft[]>([]);
  const [pos, setPos] = useState<PurchaseOrder[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [tab, setTab] = useState<Tab>("inspections");

  useEffect(() => {
    if (!id) return;
    api.getProject(id).then(setProject);
    api.listInspections().then((all) => setInspections(all.filter((i) => String(i.project_id) === id)));
    api.listInvoices().then((all) => setInvoices(all.filter((i) => String(i.project_id) === id)));
    api.listPurchaseOrders().then((all) => setPos(all.filter((p) => String(p.project_id) === id)));
    api.listVendors().then(setVendors);
    api.getAnalytics().then(setAnalytics);
  }, [id]);

  if (!project) return <p className="text-gray-500">Loading…</p>;

  const vendorName = (vendorId: number) => vendors.find((v) => v.id === vendorId)?.company_name ?? `Vendor ${vendorId}`;
  const budget = analytics?.project_budgets.find((b) => b.project_id === project.id);

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{project.name}</h1>
          <p className="text-gray-500">
            {project.client_name} · {project.site_location}
          </p>
        </div>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            project.status === "completed" ? "bg-blue-100 text-blue-700" : "bg-green-100 text-green-700"
          }`}
        >
          {project.status}
        </span>
      </div>

      <div className="mt-3 flex gap-6 text-sm text-gray-600">
        <span>Total panels: {project.total_panels}</span>
        <span>Contract value: {formatMYR(project.contract_value)}</span>
        <span className="capitalize">Region: {project.region}</span>
      </div>

      {budget && (
        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="flex items-center justify-between text-sm text-gray-500">
              <span>Build progress</span>
              <span className="font-medium text-gray-900">{budget.completion_pct}%</span>
            </div>
            <div className="mt-2">
              <ProgressBar pct={budget.completion_pct} />
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="flex items-center justify-between text-sm text-gray-500">
              <span>Budget used ({formatMYR(budget.spend)} of {formatMYR(budget.contract_value)})</span>
              <span className="font-medium text-gray-900">{budget.budget_used_pct}%</span>
            </div>
            <div className="mt-2">
              <ProgressBar pct={budget.budget_used_pct} colorClass={budget.budget_used_pct > 80 ? "bg-orange-500" : "bg-blue-600"} />
            </div>
          </div>
        </div>
      )}

      <div className="mt-6 border-b border-gray-200 flex gap-6">
        {(["inspections", "invoices", "pos"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 text-sm font-medium border-b-2 -mb-px ${
              tab === t ? "border-green-600 text-green-700" : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            {t === "inspections" && `Inspections (${inspections.length})`}
            {t === "invoices" && `Invoice Drafts (${invoices.length})`}
            {t === "pos" && `Purchase Orders (${pos.length})`}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "inspections" && (
          <div className="space-y-3">
            {inspections.length === 0 && <p className="text-sm text-gray-400">No inspections yet.</p>}
            {inspections.map((insp) => (
              <div key={insp.id} className="rounded-lg border border-gray-200 bg-white p-4">
                <div className="flex justify-between text-sm text-gray-600">
                  <span>{insp.panels_detected} panels detected</span>
                  <span>{insp.panels_with_issues} issues</span>
                </div>
                <div className="mt-2">
                  <ProgressBar pct={insp.completion_pct ?? 0} />
                </div>
                <p className="mt-1 text-xs text-gray-500">{insp.completion_pct ?? 0}% complete</p>
                {insp.issues.length > 0 && (
                  <ul className="mt-2 list-inside list-disc text-xs text-orange-600">
                    {insp.issues.map((issue, idx) => (
                      <li key={idx}>{issue}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}

        {tab === "invoices" && (
          <div className="space-y-3">
            {invoices.length === 0 && <p className="text-sm text-gray-400">No invoice drafts yet.</p>}
            {invoices.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4">
                <div>
                  <p className="font-medium text-gray-900">{inv.invoice_number}</p>
                  <p className="text-sm text-gray-500">{inv.claim_percentage}% claim</p>
                </div>
                <div className="text-right">
                  <p className="font-medium text-gray-900">{formatMYR(inv.claim_amount_myr)}</p>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      inv.status === "approved"
                        ? "bg-green-100 text-green-700"
                        : inv.status === "sent"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    {inv.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "pos" && (
          <div className="space-y-3">
            {pos.length === 0 && <p className="text-sm text-gray-400">No purchase orders yet.</p>}
            {pos.map((po) => (
              <div key={po.id} className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4">
                <div>
                  <p className="font-medium text-gray-900">{po.po_number}</p>
                  <p className="text-sm text-gray-500">
                    {po.item_description} × {po.quantity}
                  </p>
                  <p className="text-xs text-gray-400">{vendorName(po.vendor_id)}</p>
                </div>
                <div className="text-right">
                  <p className="font-medium text-gray-900">{formatMYR(po.total_price_myr)}</p>
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                    {po.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
