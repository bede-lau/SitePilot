import { FolderKanban, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, EmptyState, Progress, Skeleton } from "../components/ui";
import { api, formatMYR, type AnalyticsOverview, type Project } from "../lib/api";

export default function ProjectsList() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [search, setSearch] = useState("");
  const [region, setRegion] = useState("all");
  const [status, setStatus] = useState("all");

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
    api.getAnalytics().then(setAnalytics).catch(() => {});
  }, []);

  const budgetByProject = useMemo(() => new Map(analytics?.project_budgets.map((b) => [b.project_id, b]) ?? []), [analytics]);
  const regions = useMemo(() => Array.from(new Set((projects ?? []).map((p) => p.region))).sort(), [projects]);

  const filtered = (projects ?? []).filter((p) => {
    const matchesSearch = !search || [p.name, p.client_name, p.site_location].some((s) => s.toLowerCase().includes(search.toLowerCase()));
    const matchesRegion = region === "all" || p.region === region;
    const matchesStatus = status === "all" || p.status === status;
    return matchesSearch && matchesRegion && matchesStatus;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text">Projects</h1>
        <p className="mt-1 text-sm text-muted">{projects ? `${filtered.length} of ${projects.length}` : "Loading…"}</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-subtle" aria-hidden="true" />
          <input
            type="text"
            placeholder="Search by name, client, or site…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search projects"
            className="w-full rounded-md border border-border bg-surface py-2 pl-8 pr-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          aria-label="Filter by region"
          className="rounded-md border border-border bg-surface px-3 py-2 text-sm capitalize text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
        >
          <option value="all">All regions</option>
          {regions.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
          className="rounded-md border border-border bg-surface px-3 py-2 text-sm capitalize text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      {!projects ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="rect" height={180} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={<FolderKanban />} title="No projects match your filters" body="Try clearing the search or filters above." />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((project) => {
            const budget = budgetByProject.get(project.id);
            return (
              <Link key={project.id} to={`/projects/${project.id}`} className="block">
                <Card elevation="sm" interactive className="h-full p-5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h2 className="truncate font-semibold text-text">{project.name}</h2>
                      <p className="truncate text-sm text-muted">{project.client_name}</p>
                      <p className="truncate text-sm text-muted">{project.site_location}</p>
                    </div>
                    <Badge variant={project.status === "completed" ? "info" : "success"}>{project.status}</Badge>
                  </div>

                  {budget && (
                    <div className="mt-4 space-y-2">
                      <Progress label="Build progress" value={budget.completion_pct} showValue />
                      <Progress label="Budget used" value={budget.budget_used_pct} showValue tone={budget.budget_used_pct > 80 ? "warning" : "accent"} />
                    </div>
                  )}

                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-sm font-medium tabular-nums text-text">{formatMYR(project.contract_value)}</span>
                    <Badge variant="neutral">{project.region}</Badge>
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
