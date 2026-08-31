import { formatKwh, formatMYR, formatYearRange } from "../../lib/format";
import { AreaChart } from "../charts";
import { Card, CardBody, CardHeader } from "../ui";
import type { FinancialModel } from "../../lib/types";

/** Monthly savings headline, payback shown as a range (never a single figure), a 25-year
 * cumulative-net area chart, a before/after bill comparison, and the assumptions in small print. */
export function FinancialCard({ financial }: { financial: FinancialModel }) {
  const chartData = financial.projection.map((p) => ({ label: `Yr ${p.year}`, value: p.cumulative_net }));

  return (
    <Card elevation="sm">
      <CardHeader>
        <p className="text-sm font-semibold text-text">Financial projection</p>
      </CardHeader>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-subtle">Monthly savings</p>
            <p className="text-2xl font-semibold tabular-nums text-success">{formatMYR(financial.monthly_savings_myr)}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-subtle">Payback</p>
            <p className="text-lg font-semibold tabular-nums text-text">{formatYearRange(financial.payback_range_years)}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-subtle">System cost</p>
            <p className="text-lg font-semibold tabular-nums text-text">
              {formatMYR(financial.cost_range_myr?.[0])} – {formatMYR(financial.cost_range_myr?.[1])}
            </p>
          </div>
        </div>

        <div>
          <p className="mb-1.5 text-xs font-medium text-muted">25-year cumulative net (RM)</p>
          <AreaChart data={chartData} tone="chart-3" valueFormatter={(v) => formatMYR(v)} ariaLabel="Cumulative net savings over 25 years" height={160} />
        </div>

        <div className="grid grid-cols-2 gap-3 rounded-lg border border-border bg-bg-subtle/50 p-3 text-sm">
          <div>
            <p className="text-[11px] text-subtle">Bill before</p>
            <p className="font-medium tabular-nums text-text">{formatMYR(financial.bill_before_myr)}</p>
          </div>
          <div>
            <p className="text-[11px] text-subtle">Bill after</p>
            <p className="font-medium tabular-nums text-success">{formatMYR(financial.bill_after_myr)}</p>
          </div>
          <div>
            <p className="text-[11px] text-subtle">Monthly generation</p>
            <p className="font-medium tabular-nums text-text">{formatKwh(financial.monthly_generation_kwh)}</p>
          </div>
          <div>
            <p className="text-[11px] text-subtle">Annual savings</p>
            <p className="font-medium tabular-nums text-text">{formatMYR(financial.annual_savings_myr)}</p>
          </div>
        </div>

        {financial.assumptions.length > 0 && (
          <ul className="space-y-0.5 text-[11px] text-subtle">
            {financial.assumptions.map((a, i) => (
              <li key={i}>· {a}</li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
