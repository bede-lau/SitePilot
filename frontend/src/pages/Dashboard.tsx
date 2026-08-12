import { useEffect, useState } from "react";
import ActivityFeed from "../components/ActivityFeed";
import BarChart from "../components/BarChart";
import StatCard from "../components/StatCard";
import { useActivityFeed } from "../hooks/useActivityFeed";
import { api, formatMYR, type AnalyticsOverview } from "../lib/api";

function isThisMonth(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
}

function monthLabel(key: string): string {
  const [year, month] = key.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-MY", { month: "short", year: "2-digit" });
}

export default function Dashboard() {
  const events = useActivityFeed();
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [counts, setCounts] = useState({
    activeProjects: 0,
    inspectionsThisMonth: 0,
    invoicesPending: 0,
    posThisMonth: 0,
  });

  useEffect(() => {
    Promise.all([api.listProjects(), api.listInspections(), api.listInvoices(), api.listPurchaseOrders()]).then(
      ([projects, inspections, invoices, pos]) => {
        setCounts({
          activeProjects: projects.filter((p) => p.status === "active").length,
          inspectionsThisMonth: inspections.filter((i) => isThisMonth(i.created_at)).length,
          invoicesPending: invoices.filter((i) => i.status !== "approved").length,
          posThisMonth: pos.filter((p) => isThisMonth(p.created_at)).length,
        });
      },
    );
    api.getAnalytics().then(setAnalytics);
  }, []);

  useEffect(() => {
    const latest = events[0];
    if (!latest) return;
    setCounts((prev) => {
      switch (latest.event_type) {
        case "inspection_created":
          return { ...prev, inspectionsThisMonth: prev.inspectionsThisMonth + 1 };
        case "invoice_created":
          return { ...prev, invoicesPending: prev.invoicesPending + 1 };
        case "po_created":
          return { ...prev, posThisMonth: prev.posThisMonth + 1 };
        default:
          return prev;
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events.length]);

  const budgetUsedPct = analytics && analytics.total_contract_value
    ? Math.round((analytics.total_spend / analytics.total_contract_value) * 100)
    : 0;

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900">FieldBot Operations Portal</h1>
      <p className="mt-1 text-sm text-gray-500">Real-time view across all active solar projects.</p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active Projects" value={counts.activeProjects} />
        <StatCard label="Inspections This Month" value={counts.inspectionsThisMonth} />
        <StatCard label="Invoices Pending" value={counts.invoicesPending} />
        <StatCard label="POs This Month" value={counts.posThisMonth} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-900">Budget Burn by Project</h2>
            {analytics && (
              <span className="text-sm text-gray-500">
                {formatMYR(analytics.total_spend)} / {formatMYR(analytics.total_contract_value)} ({budgetUsedPct}%)
              </span>
            )}
          </div>
          <div className="mt-4">
            <BarChart
              data={(analytics?.project_budgets ?? []).map((p) => ({ label: p.name, value: p.budget_used_pct }))}
              formatValue={(v) => `${v.toFixed(0)}%`}
              color="bg-blue-600"
            />
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-medium text-gray-900">Top Vendors by Spend</h2>
          <div className="mt-4">
            <BarChart
              data={(analytics?.vendor_leaderboard ?? []).slice(0, 5).map((v) => ({ label: v.company_name, value: v.total_spend }))}
              formatValue={(v) => formatMYR(v)}
            />
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h2 className="text-lg font-medium text-gray-900">Monthly Spend</h2>
          <div className="mt-4">
            <BarChart
              data={(analytics?.spend_trend ?? []).map((s) => ({ label: monthLabel(s.month), value: s.amount }))}
              formatValue={(v) => formatMYR(v)}
              color="bg-purple-600"
            />
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-medium text-gray-900">Quality Watch</h2>
          <p className="mt-3 text-sm text-gray-500">Panels flagged with issues across all projects.</p>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{analytics?.total_panels_with_issues ?? 0}</p>
          <p className="mt-1 text-xs text-gray-400">From AI inspection reports site managers submitted via Telegram.</p>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-lg font-medium text-gray-900 mb-3">Live Activity</h2>
        <ActivityFeed events={events} />
      </div>
    </div>
  );
}
