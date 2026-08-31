import { Badge, Card, CardBody, CardHeader } from "../ui";
import type { ComponentRow } from "../../lib/types";

function isComponentRow(x: unknown): x is ComponentRow {
  return typeof x === "object" && x !== null && "kind" in x && "manufacturer" in x && "model" in x;
}

function extractComponents(data: unknown): ComponentRow[] {
  if (Array.isArray(data)) return data.filter(isComponentRow);
  if (isComponentRow(data)) return [data];
  const obj = data as { component?: unknown; components?: unknown } | null;
  if (obj && isComponentRow(obj.component)) return [obj.component];
  if (obj && Array.isArray(obj.components)) return obj.components.filter(isComponentRow);
  return [];
}

export function ComponentPickCard({ data }: { data: unknown }) {
  const components = extractComponents(data);

  return (
    <Card elevation="sm">
      <CardHeader>
        <p className="text-sm font-semibold text-text">{components.length > 1 ? "Component options" : "Component"}</p>
      </CardHeader>
      <CardBody className="space-y-2">
        {components.map((c) => (
          <div key={c.id} className="rounded-lg border border-border bg-bg-subtle/40 px-3 py-2.5">
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-sm font-medium text-text">
                {c.manufacturer} {c.model}
              </p>
              {c.tier != null && <Badge variant={c.tier === 1 ? "success" : "neutral"}>Tier {c.tier}</Badge>}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-muted">
              {c.kind === "module" && (
                <>
                  <span>{c.rated_wp ?? "—"} Wp</span>
                  <span>Vmp {c.vmp ?? "—"}V</span>
                  <span>Voc {c.voc ?? "—"}V</span>
                  <span>{c.efficiency_pct ?? "—"}% eff.</span>
                </>
              )}
              {c.kind === "inverter" && (
                <>
                  <span>{c.ac_rating_kw ?? "—"} kW AC</span>
                  <span>
                    MPPT {c.mppt_min_v ?? "—"}–{c.mppt_max_v ?? "—"}V
                  </span>
                  <span>
                    {c.mppt_count ?? "—"} MPPT{(c.mppt_count ?? 0) > 1 ? "s" : ""}
                  </span>
                </>
              )}
            </div>
          </div>
        ))}
        {components.length === 0 && <p className="py-4 text-center text-xs text-muted">No component data.</p>}
      </CardBody>
    </Card>
  );
}
