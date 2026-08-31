import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { BosSpecCard, FeasibilityCard, FinancialCard, QuoteCard } from "../components/cards";
import { Badge, Card, CardBody, EmptyState, Progress, Skeleton, Tab, TabList, TabPanel, Tabs } from "../components/ui";
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
import type { DesignReport, SupplierQuote } from "../lib/types";

type SectionTab = "design" | "quotes" | "financials" | "inspections" | "invoices" | "pos";

export default function ProjectDetail() {
  const { id } = useParams();
  const [project, setProject] = useState<ProjectDetailType | null>(null);
  const [inspections, setInspections] = useState<InspectionReport[]>([]);
  const [invoices, setInvoices] = useState<InvoiceDraft[]>([]);
  const [pos, setPos] = useState<PurchaseOrder[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [runs, setRuns] = useState<DesignReport[]>([]);
  const [quotes, setQuotes] = useState<SupplierQuote[]>([]);
  const [tab, setTab] = useState<SectionTab>("design");
  const [projectError, setProjectError] = useState(false);

  useEffect(() => {
    if (!id) return;
    const numericId = Number(id);
    setProjectError(false);
    api
      .getProject(id)
      .then(setProject)
      .catch(() => setProjectError(true));
    api
      .listInspections()
      .then((all) => setInspections(all.filter((i) => String(i.project_id) === id)))
      .catch(() => setInspections([]));
    api
      .listInvoices()
      .then((all) => setInvoices(all.filter((i) => String(i.project_id) === id)))
      .catch(() => setInvoices([]));
    api
      .listPurchaseOrders()
      .then((all) => setPos(all.filter((p) => String(p.project_id) === id)))
      .catch(() => setPos([]));
    api.listVendors().then(setVendors).catch(() => setVendors([]));
    api.getAnalytics().then(setAnalytics).catch(() => {});
    api
      .listFeasibilityRuns(numericId)
      .then(setRuns)
      .catch(() => setRuns([]));
    api
      .listQuotes()
      .then(setQuotes)
      .catch(() => setQuotes([]));
  }, [id]);

  if (!project) {
    if (projectError) {
      return <EmptyState title="Couldn't load this project" body="The backend may not be running, or this project doesn't exist." />;
    }
    return (
      <div className="space-y-4">
        <Skeleton variant="text" width={280} height={28} />
        <Skeleton variant="rect" height={120} />
      </div>
    );
  }

  const vendorName = (vendorId: number) => vendors.find((v) => v.id === vendorId)?.company_name ?? `Vendor ${vendorId}`;
  const budget = analytics?.project_budgets.find((b) => b.project_id === project.id);
  const latestRun = runs.length > 0 ? runs[runs.length - 1] : null;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">{project.name}</h1>
          <p className="text-sm text-muted">
            {project.client_name} · {project.site_location}
          </p>
        </div>
        <Badge variant={project.status === "completed" ? "info" : "success"}>{project.status}</Badge>
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
        <span>
          Total panels: <span className="text-text">{project.total_panels}</span>
        </span>
        <span>
          Contract value: <span className="text-text">{formatMYR(project.contract_value)}</span>
        </span>
        <span className="capitalize">
          Region: <span className="text-text">{project.region}</span>
        </span>
      </div>

      {budget && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Card elevation="sm">
            <CardBody>
              <Progress label="Build progress" value={budget.completion_pct} showValue />
            </CardBody>
          </Card>
          <Card elevation="sm">
            <CardBody>
              <Progress
                label={`Budget used (${formatMYR(budget.spend)} of ${formatMYR(budget.contract_value)})`}
                value={budget.budget_used_pct}
                showValue
                tone={budget.budget_used_pct > 80 ? "warning" : "accent"}
              />
            </CardBody>
          </Card>
        </div>
      )}

      <Tabs value={tab} onChange={(v) => setTab(v as SectionTab)}>
        <TabList aria-label="Project sections">
          <Tab value="design">Design</Tab>
          <Tab value="quotes">Quotes ({quotes.length})</Tab>
          <Tab value="financials">Financials</Tab>
          <Tab value="inspections">Inspections ({inspections.length})</Tab>
          <Tab value="invoices">Invoice Drafts ({invoices.length})</Tab>
          <Tab value="pos">Purchase Orders ({pos.length})</Tab>
        </TabList>

        <TabPanel value="design" className="mt-4 space-y-4">
          {latestRun ? (
            <>
              <FeasibilityCard report={latestRun} />
              <BosSpecCard bos={latestRun.bos} />
            </>
          ) : (
            <EmptyState title="No design run yet" body="Run a feasibility check for this project from the Feasibility workbench or chat." />
          )}
        </TabPanel>

        <TabPanel value="quotes" className="mt-4 space-y-4">
          {quotes.length === 0 ? (
            <EmptyState title="No parsed quotes" body="Drop a supplier quote in Procurement or chat to see it here." />
          ) : (
            <>
              <p className="text-xs text-subtle">Showing quotes across the workspace — the API doesn't scope parsed quotes to a project.</p>
              {quotes.map((q) => (
                <QuoteCard key={q.id} quote={q} />
              ))}
            </>
          )}
        </TabPanel>

        <TabPanel value="financials" className="mt-4">
          {latestRun ? <FinancialCard financial={latestRun.financial} /> : <EmptyState title="No financial model yet" body="Run a feasibility check to generate a payback projection." />}
        </TabPanel>

        <TabPanel value="inspections" className="mt-4 space-y-3">
          {inspections.length === 0 && <p className="text-sm text-muted">No inspections yet.</p>}
          {inspections.map((insp) => (
            <Card key={insp.id} elevation="sm">
              <CardBody>
                <div className="flex justify-between text-sm text-muted">
                  <span>{insp.panels_detected} panels detected</span>
                  <span>{insp.panels_with_issues} issues</span>
                </div>
                <Progress className="mt-2" value={insp.completion_pct ?? 0} showValue />
                {insp.issues.length > 0 && (
                  <ul className="mt-2 list-inside list-disc text-xs text-warning">
                    {insp.issues.map((issue, idx) => (
                      <li key={idx}>{issue}</li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          ))}
        </TabPanel>

        <TabPanel value="invoices" className="mt-4 space-y-3">
          {invoices.length === 0 && <p className="text-sm text-muted">No invoice drafts yet.</p>}
          {invoices.map((inv) => (
            <Card key={inv.id} elevation="sm">
              <CardBody className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-text">{inv.invoice_number}</p>
                  <p className="text-sm text-muted">{inv.claim_percentage}% claim</p>
                </div>
                <div className="text-right">
                  <p className="font-medium tabular-nums text-text">{formatMYR(inv.claim_amount_myr)}</p>
                  <Badge variant={inv.status === "approved" ? "success" : inv.status === "sent" ? "info" : "warning"}>{inv.status}</Badge>
                </div>
              </CardBody>
            </Card>
          ))}
        </TabPanel>

        <TabPanel value="pos" className="mt-4 space-y-3">
          {pos.length === 0 && <p className="text-sm text-muted">No purchase orders yet.</p>}
          {pos.map((po) => (
            <Card key={po.id} elevation="sm">
              <CardBody className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-text">{po.po_number}</p>
                  <p className="text-sm text-muted">
                    {po.item_description} × {po.quantity}
                  </p>
                  <p className="text-xs text-subtle">{vendorName(po.vendor_id)}</p>
                </div>
                <div className="text-right">
                  <p className="font-medium tabular-nums text-text">{formatMYR(po.total_price_myr)}</p>
                  <Badge variant="info">{po.status}</Badge>
                </div>
              </CardBody>
            </Card>
          ))}
        </TabPanel>
      </Tabs>
    </div>
  );
}
