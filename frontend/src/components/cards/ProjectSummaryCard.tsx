import { ArrowUpRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { formatMYR } from "../../lib/format";
import { Badge, Button, Card, CardBody, CardHeader } from "../ui";
import type { Project, ProjectDetail } from "../../lib/types";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-subtle">{label}</p>
      <p className="mt-0.5 truncate font-medium text-text">{value}</p>
    </div>
  );
}

export function ProjectSummaryCard({ project }: { project: Project | ProjectDetail }) {
  const navigate = useNavigate();
  const detail = "inspections_count" in project ? project : null;

  return (
    <Card elevation="sm">
      <CardHeader>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text">{project.name}</p>
          <p className="truncate text-xs text-muted">
            {project.client_name} · {project.site_location}
          </p>
        </div>
        <Badge variant={project.status === "completed" ? "info" : "success"}>{project.status}</Badge>
      </CardHeader>
      <CardBody className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <Field label="Panels" value={String(project.total_panels)} />
        <Field label="Contract" value={formatMYR(project.contract_value)} />
        <Field label="Region" value={project.region} />
        <Field label="Phase" value={project.phase ?? "—"} />
        {detail && (
          <>
            <Field label="Inspections" value={String(detail.inspections_count)} />
            <Field label="Invoices" value={String(detail.invoices_count)} />
            <Field label="Purchase orders" value={String(detail.purchase_orders_count)} />
          </>
        )}
      </CardBody>
      <div className="border-t border-border px-5 py-3">
        <Button size="sm" variant="secondary" iconRight={<ArrowUpRight className="size-3.5" />} onClick={() => navigate(`/projects/${project.id}`)}>
          Open project
        </Button>
      </div>
    </Card>
  );
}
