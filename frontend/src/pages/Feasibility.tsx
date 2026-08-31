import { Loader2, PlayCircle } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { BosSpecCard, FeasibilityCard, FinancialCard, PoCard } from "../components/cards";
import { Button, Card, CardBody, CardHeader, EmptyState, Segmented } from "../components/ui";
import { api } from "../lib/api";
import type { BudgetTier, ComponentRow, DesignReport, Project, SystemType } from "../lib/types";

const SYSTEM_TYPE_OPTIONS: { value: SystemType; label: string }[] = [
  { value: "on_grid", label: "On-grid" },
  { value: "hybrid", label: "Hybrid" },
];

const TIER_OPTIONS: { value: BudgetTier; label: string }[] = [
  { value: "entry", label: "Entry" },
  { value: "mid", label: "Mid" },
  { value: "premium", label: "Premium" },
];

const inputClass = "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/50";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}

/** Engineering workbench (ARD §6.3): project + component pickers feeding `POST /api/feasibility/run`,
 * then the full result — check matrix, string diagram, BOS spec, financials, PO approval. */
export default function Feasibility() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [modules, setModules] = useState<ComponentRow[]>([]);
  const [inverters, setInverters] = useState<ComponentRow[]>([]);

  const [projectId, setProjectId] = useState<number | null>(null);
  const [systemType, setSystemType] = useState<SystemType>("on_grid");
  const [panelCount, setPanelCount] = useState("");
  const [moduleId, setModuleId] = useState<number | null>(null);
  const [inverterId, setInverterId] = useState<number | null>(null);
  const [tier, setTier] = useState<BudgetTier>("mid");
  const [monthlyConsumption, setMonthlyConsumption] = useState("");

  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<DesignReport | null>(null);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => setProjects([]));
    api.listComponents({ kind: "module", limit: 100 }).then(setModules).catch(() => setModules([]));
    api.listComponents({ kind: "inverter", limit: 100 }).then(setInverters).catch(() => setInverters([]));
  }, []);

  const selectedProject = useMemo(() => projects.find((p) => p.id === projectId) ?? null, [projects, projectId]);

  useEffect(() => {
    if (!selectedProject) return;
    if (selectedProject.system_type) setSystemType(selectedProject.system_type);
    if (selectedProject.monthly_consumption_kwh) setMonthlyConsumption(String(selectedProject.monthly_consumption_kwh));
    if (selectedProject.total_panels) setPanelCount(String(selectedProject.total_panels));
  }, [selectedProject]);

  async function run() {
    if (!projectId) {
      setError("Choose a project first.");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const result = await api.runFeasibility({
        project_id: projectId,
        system_type: systemType,
        panel_count: panelCount ? Number(panelCount) : undefined,
        module: moduleId ? { component_id: moduleId } : undefined,
        inverter: inverterId ? { component_id: inverterId } : undefined,
        monthly_consumption_kwh: monthlyConsumption ? Number(monthlyConsumption) : undefined,
        budget_tier: tier,
      });
      setReport(result);
    } catch {
      setError("Feasibility run failed — check the inputs and that the backend is reachable.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text">Feasibility workbench</h1>
        <p className="mt-1 text-sm text-muted">Deterministic string sizing, MPPT matching, and BOS spec generation.</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[340px_1fr]">
        <Card elevation="sm" className="h-fit lg:sticky lg:top-8">
          <CardHeader>
            <p className="text-sm font-semibold text-text">Design inputs</p>
          </CardHeader>
          <CardBody className="space-y-4">
            <Field label="Project">
              <select className={inputClass} value={projectId ?? ""} onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Select a project…</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="System type">
              <Segmented aria-label="System type" options={SYSTEM_TYPE_OPTIONS} value={systemType} onChange={setSystemType} />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Panel count">
                <input type="number" min={1} className={inputClass} value={panelCount} onChange={(e) => setPanelCount(e.target.value)} placeholder="e.g. 20" />
              </Field>

              <Field label="Monthly kWh">
                <input type="number" min={0} className={inputClass} value={monthlyConsumption} onChange={(e) => setMonthlyConsumption(e.target.value)} placeholder="e.g. 950" />
              </Field>
            </div>

            <Field label="Module">
              <select className={inputClass} value={moduleId ?? ""} onChange={(e) => setModuleId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Auto-select best fit</option>
                {modules.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.manufacturer} {m.model} ({m.rated_wp}Wp)
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Inverter">
              <select className={inputClass} value={inverterId ?? ""} onChange={(e) => setInverterId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Auto-select best fit</option>
                {inverters.map((inv) => (
                  <option key={inv.id} value={inv.id}>
                    {inv.manufacturer} {inv.model} ({inv.ac_rating_kw}kW)
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Equipment tier">
              <Segmented aria-label="Equipment tier" options={TIER_OPTIONS} value={tier} onChange={setTier} />
            </Field>

            {error && <p className="text-xs text-danger">{error}</p>}

            <Button className="w-full" onClick={run} loading={running} iconLeft={!running ? <PlayCircle className="size-4" /> : undefined}>
              Run feasibility
            </Button>
          </CardBody>
        </Card>

        <div className="min-w-0 space-y-4">
          {running && !report && (
            <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-border bg-surface py-16 text-sm text-muted">
              <Loader2 className="size-5 animate-spin text-accent" aria-hidden="true" />
              Running string sizing, MPPT checks, and BOS generation…
            </div>
          )}
          {!running && !report && (
            <EmptyState title="No design run yet" body="Pick a project and run the workbench to see the check matrix, string diagram, and BOS spec." />
          )}
          {report && (
            <>
              <FeasibilityCard report={report} />
              <BosSpecCard bos={report.bos} />
              <FinancialCard financial={report.financial} />
              <PoCard report={report} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
