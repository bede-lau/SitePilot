import { CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import { cn } from "../../lib/cn";
import { formatKwp, formatPct } from "../../lib/format";
import { Badge, Card, CardBody, CardHeader, Tab, TabList, TabPanel, Tabs } from "../ui";
import { MpptWindowBar, RangeMeter } from "../charts";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { StringDiagram } from "./StringDiagram";
import type { Check, DesignReport } from "../../lib/types";

function CheckRow({ check }: { check: Check }) {
  return (
    <li className="flex items-center gap-3 border-b border-border py-2.5 last:border-0">
      {check.passed ? <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden="true" /> : <XCircle className="size-4 shrink-0 text-danger" aria-hidden="true" />}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-text">{check.label}</p>
        <p className="text-xs text-muted">Expected {check.expected}</p>
      </div>
      <div className="shrink-0 text-right">
        <p className={cn("text-sm font-medium tabular-nums", check.passed ? "text-text" : "text-danger")}>
          {typeof check.actual === "number" ? check.actual.toLocaleString("en-MY") : check.actual} {check.unit}
        </p>
        {check.margin_pct !== null && (
          <p className={cn("text-[11px] tabular-nums", check.margin_pct >= 0 ? "text-success" : "text-danger")}>
            {check.margin_pct >= 0 ? "+" : ""}
            {check.margin_pct.toFixed(1)}% margin
          </p>
        )}
      </div>
    </li>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-bg-subtle/60 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-subtle">{label}</p>
      <p className="mt-0.5 font-semibold tabular-nums text-text">{value}</p>
    </div>
  );
}

/** The engineering centrepiece: string diagram, MPPT window plot, DC:AC range meter, and a
 * pass/fail check matrix grouped by strings / inverter / battery. */
export function FeasibilityCard({ report }: { report: DesignReport }) {
  const [tab, setTab] = useState<"strings" | "inverter" | "battery">("strings");
  const statusTone = report.status === "pass" ? "success" : report.status === "warn" ? "warning" : "danger";

  return (
    <Card elevation="sm">
      <CardHeader>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text">Feasibility — {report.strings.config_label}</p>
          <p className="truncate text-xs text-muted">
            {report.array.module.manufacturer} {report.array.module.model} → {report.inverter.manufacturer} {report.inverter.model}
          </p>
        </div>
        <Badge variant={statusTone}>{report.status}</Badge>
      </CardHeader>

      <CardBody className="space-y-5">
        <ConfidenceBadge confidence={report.confidence} size="sm" />

        <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
          <Stat label="Array size" value={formatKwp(report.array.actual_kwp)} />
          <Stat label="Coverage" value={formatPct(report.array.coverage_pct)} />
          <Stat label="Panels" value={String(report.array.panel_count)} />
          <Stat label="DC:AC" value={`${report.inverter.dc_ac_ratio.toFixed(2)}x`} />
        </div>

        <StringDiagram
          series={report.strings.series}
          parallel={report.strings.parallel}
          vmpString={report.strings.vmp_string}
          vocString={report.strings.voc_string}
          moduleLabel={`${report.array.module.manufacturer} ${report.array.module.model}`}
          inverterLabel={report.inverter.model}
        />

        <MpptWindowBar
          mpptMinV={report.inverter.mppt_min_v}
          mpptMaxV={report.inverter.mppt_max_v}
          maxDcVoltageV={report.inverter.max_dc_voltage_v}
          vmpString={report.strings.vmp_string}
          vocString={report.strings.voc_string}
          vocColdString={report.strings.voc_cold_string}
          ariaLabel="Inverter MPPT operating window"
        />

        <RangeMeter
          value={report.inverter.dc_ac_ratio}
          min={0.8}
          max={1.8}
          bandMin={1.2}
          bandMax={1.5}
          label="DC:AC ratio"
          valueFormatter={(v) => `${v.toFixed(2)}x`}
          ariaLabel="DC to AC ratio"
        />

        <Tabs value={tab} onChange={(v) => setTab(v as typeof tab)}>
          <TabList aria-label="Check groups">
            <Tab value="strings">Strings ({report.strings.checks.length})</Tab>
            <Tab value="inverter">Inverter ({report.inverter.checks.length})</Tab>
            {report.battery && <Tab value="battery">Battery ({report.battery.checks.length})</Tab>}
          </TabList>
          <TabPanel value="strings">
            <ul>
              {report.strings.checks.map((c) => (
                <CheckRow key={c.id} check={c} />
              ))}
            </ul>
          </TabPanel>
          <TabPanel value="inverter">
            <ul>
              {report.inverter.checks.map((c) => (
                <CheckRow key={c.id} check={c} />
              ))}
            </ul>
          </TabPanel>
          {report.battery && (
            <TabPanel value="battery">
              <ul>
                {report.battery.checks.map((c) => (
                  <CheckRow key={c.id} check={c} />
                ))}
              </ul>
            </TabPanel>
          )}
        </Tabs>

        {report.warnings.length > 0 && (
          <div className="space-y-1.5">
            {report.warnings.map((w, i) => (
              <div
                key={i}
                className={cn(
                  "rounded-lg border px-3 py-2 text-xs",
                  w.level === "error" ? "border-danger/30 bg-danger/10 text-danger" : w.level === "warn" ? "border-warning/30 bg-warning/10 text-warning" : "border-info/30 bg-info/10 text-info",
                )}
              >
                {w.message}
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
