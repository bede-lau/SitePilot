import { Building2, Leaf, PanelsTopLeft, ShieldCheck, Wallet, Zap } from "lucide-react";
import type { ComponentType } from "react";
import { useEffect, useState } from "react";
import { AreaChart, Sparkline, type ChartTone } from "../components/charts";
import { Card, CardBody, CardHeader, EmptyState, Skeleton, SkeletonStatCard } from "../components/ui";
import { api, formatMYR } from "../lib/api";
import { formatKwp, formatNumber, formatPct } from "../lib/format";
import type { AnalyticsOverview, OverviewResponse } from "../lib/types";

function monthLabel(key: string): string {
  const [year, month] = key.split("-").map(Number);
  if (!year || !month) return key;
  return new Date(year, month - 1, 1).toLocaleDateString("en-MY", { month: "short", year: "2-digit" });
}

interface StatTileProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  trend?: number[];
  tone?: ChartTone;
}

function StatTile({ icon: Icon, label, value, trend, tone = "chart-1" }: StatTileProps) {
  return (
    <Card elevation="sm">
      <CardBody className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-start gap-1.5 text-subtle">
            <Icon className="mt-px size-3.5 shrink-0" />
            <p className="text-xs leading-tight">{label}</p>
          </div>
          <p className="mt-1.5 text-xl font-semibold tabular-nums text-text">{value}</p>
        </div>
        {trend && trend.length > 1 && (
          <Sparkline data={trend} tone={tone} ariaLabel={`${label} trend`} width={64} height={28} className="hidden shrink-0 sm:block" />
        )}
      </CardBody>
    </Card>
  );
}

/** Command Center — KPI rail, generation + spend trends, live activity feed, and project status
 * (ARD §6.3). The docked chat panel lives in Layout, not here. */
export default function Dashboard() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    Promise.allSettled([api.getOverview(), api.getAnalytics()]).then(([ov, an]) => {
      if (ov.status === "fulfilled") setOverview(ov.value);
      else setFailed(true);
      if (an.status === "fulfilled") setAnalytics(an.value);
      setLoading(false);
    });
  }, []);

  const generationTrend = overview?.generation_trend ?? [];
  const spendTrend = overview?.spend_trend ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text">Command Center</h1>
        <p className="mt-1 text-sm text-muted">Real-time view across every active solar project.</p>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 2xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonStatCard key={i} />
          ))}
        </div>
      ) : failed ? (
        <EmptyState title="Couldn't load the overview" body="The backend may not be running. Data will appear once it's reachable." />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 2xl:grid-cols-6">
          <StatTile icon={Zap} label="Total capacity" value={formatKwp(overview?.total_capacity_kwp ?? null)} trend={generationTrend.map((p) => p.value)} tone="chart-1" />
          <StatTile icon={Building2} label="Active projects" value={formatNumber(overview?.active_projects ?? null)} tone="chart-2" />
          <StatTile icon={ShieldCheck} label="Avg. confidence" value={formatPct(overview?.avg_confidence ?? null)} tone="chart-3" />
          <StatTile icon={Wallet} label="PO value" value={formatMYR(overview?.po_value_myr ?? null)} trend={spendTrend.map((p) => p.value)} tone="chart-4" />
          <StatTile icon={PanelsTopLeft} label="Panels installed" value={formatNumber(overview?.panels_installed ?? null)} tone="chart-2" />
          <StatTile icon={Leaf} label="CO₂ avoided" value={`${formatNumber(overview?.co2_avoided_tonnes ?? null, { decimals: 1 })} t`} tone="chart-3" />
        </div>
      )}

      <Card elevation="sm">
        <CardHeader>
          <p className="text-sm font-semibold text-text">Generation trend</p>
          <span className="text-xs text-muted">kWh / month</span>
        </CardHeader>
        <CardBody>
          {loading ? (
            <Skeleton variant="rect" height={220} />
          ) : (
            <AreaChart
              data={generationTrend.map((p) => ({ label: monthLabel(p.month), value: p.value }))}
              tone="chart-1"
              valueFormatter={(v) => `${formatNumber(v)} kWh`}
              ariaLabel="Monthly generation trend"
            />
          )}
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card elevation="sm">
          <CardHeader>
            <p className="text-sm font-semibold text-text">Spend trend</p>
            <span className="text-xs text-muted">RM / month</span>
          </CardHeader>
          <CardBody>
            {loading ? (
              <Skeleton variant="rect" height={200} />
            ) : (
              <AreaChart data={spendTrend.map((p) => ({ label: monthLabel(p.month), value: p.value }))} tone="chart-4" valueFormatter={(v) => formatMYR(v)} ariaLabel="Monthly spend trend" height={200} />
            )}
          </CardBody>
        </Card>

        <Card elevation="sm">
          <CardHeader>
            <p className="text-sm font-semibold text-text">Project status</p>
          </CardHeader>
          <CardBody className="space-y-3">
            {(analytics?.project_budgets ?? []).length === 0 && <p className="text-sm text-muted">No projects yet.</p>}
            {(analytics?.project_budgets ?? []).map((p) => (
              <div key={p.project_id} className="flex items-center justify-between gap-3 text-sm">
                <span className="min-w-0 truncate text-text">{p.name}</span>
                <span className="shrink-0 tabular-nums text-muted">{p.completion_pct}% built</span>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
