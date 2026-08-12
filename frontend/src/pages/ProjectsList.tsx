import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import ProgressBar from "../components/ProgressBar";
import { api, formatMYR, type AnalyticsOverview, type Project } from "../lib/api";

export default function ProjectsList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [search, setSearch] = useState("");
  const [region, setRegion] = useState("all");
  const [status, setStatus] = useState("all");

  useEffect(() => {
    api.listProjects().then(setProjects);
    api.getAnalytics().then(setAnalytics);
  }, []);

  const budgetByProject = useMemo(
    () => new Map(analytics?.project_budgets.map((b) => [b.project_id, b]) ?? []),
    [analytics],
  );

  const regions = useMemo(() => Array.from(new Set(projects.map((p) => p.region))).sort(), [projects]);

  const filtered = projects.filter((p) => {
    const matchesSearch =
      !search ||
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.client_name.toLowerCase().includes(search.toLowerCase()) ||
      p.site_location.toLowerCase().includes(search.toLowerCase());
    const matchesRegion = region === "all" || p.region === region;
    const matchesStatus = status === "all" || p.status === status;
    return matchesSearch && matchesRegion && matchesStatus;
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900">Projects</h1>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="text"
          placeholder="Search by name, client, or site…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-xs rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
        />
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm capitalize focus:outline-none focus:ring-2 focus:ring-green-500"
        >
          <option value="all">All regions</option>
          {regions.map((r) => (
            <option key={r} value={r} className="capitalize">
              {r}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm capitalize focus:outline-none focus:ring-2 focus:ring-green-500"
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
        </select>
        <span className="text-sm text-gray-400">{filtered.length} of {projects.length}</span>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((project) => {
          const budget = budgetByProject.get(project.id);
          return (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">{project.name}</h2>
                  <p className="text-sm text-gray-500">{project.client_name}</p>
                  <p className="text-sm text-gray-500">{project.site_location}</p>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    project.status === "completed" ? "bg-blue-100 text-blue-700" : "bg-green-100 text-green-700"
                  }`}
                >
                  {project.status}
                </span>
              </div>

              {budget && (
                <div className="mt-4 space-y-1.5">
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>Build progress</span>
                    <span className="font-medium text-gray-900">{budget.completion_pct}%</span>
                  </div>
                  <ProgressBar pct={budget.completion_pct} />
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>Budget used</span>
                    <span className="font-medium text-gray-900">{budget.budget_used_pct}%</span>
                  </div>
                  <ProgressBar
                    pct={budget.budget_used_pct}
                    colorClass={budget.budget_used_pct > 80 ? "bg-orange-500" : "bg-blue-600"}
                  />
                </div>
              )}

              <div className="mt-3 flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900">{formatMYR(project.contract_value)}</span>
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium capitalize text-gray-600">
                  {project.region}
                </span>
              </div>
            </Link>
          );
        })}
        {filtered.length === 0 && <p className="text-sm text-gray-400">No projects match your filters.</p>}
      </div>
    </div>
  );
}
