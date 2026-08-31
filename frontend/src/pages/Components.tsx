import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Card, CardBody, Dialog, EmptyState, Segmented, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import type { ComponentKind, ComponentRow } from "../lib/types";

const KIND_OPTIONS: { value: "all" | ComponentKind; label: string }[] = [
  { value: "all", label: "All" },
  { value: "module", label: "Modules" },
  { value: "inverter", label: "Inverters" },
];

type DetailRow = { label: string; value: string };

function fmt(v: unknown, suffix = ""): string | null {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return `${v}${suffix}`;
}

/** Full spec list for the expanded card — only rows with a value are shown. */
function detailRows(c: ComponentRow): DetailRow[] {
  const shared: [string, string | null][] = [
    ["Manufacturer", fmt(c.manufacturer)],
    ["Model", fmt(c.model)],
    ["Kind", fmt(c.kind)],
    ["Tier", c.tier != null ? `Tier ${c.tier}` : null],
  ];
  const specific: [string, string | null][] =
    c.kind === "module"
      ? [
          ["Rated power", fmt(c.rated_wp, " Wp")],
          ["Efficiency", fmt(c.efficiency_pct, "%")],
          ["Vmp", fmt(c.vmp, " V")],
          ["Voc", fmt(c.voc, " V")],
          ["Imp", fmt(c.imp, " A")],
          ["Isc", fmt(c.isc, " A")],
          ["Temp coeff Voc", fmt(c.temp_coeff_voc_pct_per_c, " %/°C")],
          ["Cell tech", fmt(c.cell_tech)],
          ["Area", fmt(c.area_m2, " m²")],
        ]
      : [
          ["AC rating", fmt(c.ac_rating_kw, " kW")],
          ["Max DC input", fmt(c.max_dc_input_kw, " kW")],
          ["MPPT range", c.mppt_min_v != null || c.mppt_max_v != null ? `${c.mppt_min_v ?? "—"}–${c.mppt_max_v ?? "—"} V` : null],
          ["Max DC voltage", fmt(c.max_dc_voltage_v, " V")],
          ["Max input current / MPPT", fmt(c.max_input_current_per_mppt_a, " A")],
          ["MPPT count", fmt(c.mppt_count)],
          ["Phase", fmt(c.phase)],
          ["Euro efficiency", fmt(c.euro_efficiency_pct, "%")],
          ["Anti-islanding", fmt(c.has_anti_islanding)],
        ];
  const tail: [string, string | null][] = [
    ["Source", fmt(c.source)],
    ["Datasheet", fmt(c.datasheet_url)],
  ];
  return [...shared, ...specific, ...tail]
    .filter((r): r is [string, string] => r[1] !== null)
    .map(([label, value]) => ({ label, value }));
}

/** Catalog browser over `/api/components` (ARD §6.3) — search + kind filter across the CEC module
 * and inverter tables the feasibility engine draws from. Click a card to expand its full spec sheet. */
export default function ComponentsPage() {
  const [kind, setKind] = useState<"all" | ComponentKind>("all");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<ComponentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ComponentRow | null>(null);

  useEffect(() => {
    setLoading(true);
    const timeout = setTimeout(() => {
      api
        .listComponents({ kind: kind === "all" ? undefined : kind, q: query || undefined, limit: 200 })
        .then(setRows)
        .catch(() => setRows([]))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(timeout);
  }, [kind, query]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text">Component catalog</h1>
        <p className="mt-1 text-sm text-muted">CEC-sourced modules and inverters used by the feasibility engine.</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-subtle" aria-hidden="true" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search manufacturer or model…"
            aria-label="Search components"
            className="w-full rounded-md border border-border bg-surface py-2 pl-8 pr-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>
        <Segmented aria-label="Component kind" options={KIND_OPTIONS} value={kind} onChange={setKind} />
        <span className="text-xs text-muted">{rows.length} results</span>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="rect" height={110} />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState title="No components found" body="Try a different search term or switch kind." />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((c) => (
            <Card
              key={c.id}
              elevation="sm"
              interactive
              role="button"
              tabIndex={0}
              aria-label={`${c.manufacturer} ${c.model} — view full specs`}
              onClick={() => setSelected(c)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelected(c);
                }
              }}
              className="cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
            >
              <CardBody>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text">{c.manufacturer}</p>
                    <p className="truncate text-xs text-muted">{c.model}</p>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Badge variant="neutral">{c.kind}</Badge>
                    {c.tier != null && <Badge variant={c.tier === 1 ? "success" : "neutral"}>Tier {c.tier}</Badge>}
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted">
                  {c.kind === "module" ? (
                    <>
                      <span>{c.rated_wp ?? "—"} Wp</span>
                      <span>{c.efficiency_pct ?? "—"}% eff.</span>
                      <span>Vmp {c.vmp ?? "—"}V</span>
                      <span>Voc {c.voc ?? "—"}V</span>
                    </>
                  ) : (
                    <>
                      <span>{c.ac_rating_kw ?? "—"} kW AC</span>
                      <span>{c.mppt_count ?? "—"} MPPT</span>
                      <span>
                        MPPT {c.mppt_min_v ?? "—"}–{c.mppt_max_v ?? "—"}V
                      </span>
                      <span>{c.euro_efficiency_pct ?? "—"}% eff.</span>
                    </>
                  )}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      <Dialog
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title={selected ? `${selected.manufacturer} ${selected.model}` : ""}
        description={selected ? `${selected.kind}${selected.tier != null ? ` · Tier ${selected.tier}` : ""}` : undefined}
        size="md"
      >
        {selected && (
          <dl className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
            {detailRows(selected).map((r) => (
              <div key={r.label} className="min-w-0">
                <dt className="text-xs text-muted">{r.label}</dt>
                {r.label === "Datasheet" ? (
                  <dd className="truncate text-sm text-text">
                    <a
                      href={r.value}
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent underline hover:no-underline"
                    >
                      Open datasheet
                    </a>
                  </dd>
                ) : (
                  <dd className="break-words text-sm text-text">{r.value}</dd>
                )}
              </div>
            ))}
          </dl>
        )}
      </Dialog>
    </div>
  );
}
