import { useNavigate } from "react-router-dom";
import { formatPct } from "../../lib/format";
import { Badge, Card, CardBody, CardHeader } from "../ui";
import type { Vendor } from "../../lib/types";

export function VendorListCard({ vendors }: { vendors: Vendor[] }) {
  const navigate = useNavigate();
  return (
    <Card elevation="sm">
      <CardHeader>
        <p className="text-sm font-semibold text-text">Matching vendors</p>
        <span className="text-xs text-muted">{vendors.length} found</span>
      </CardHeader>
      <CardBody className="space-y-2">
        {vendors.map((v) => (
          <button
            key={v.id}
            type="button"
            onClick={() => navigate("/vendors")}
            className="flex w-full items-center justify-between gap-3 rounded-lg border border-border bg-bg-subtle/40 px-3 py-2.5 text-left transition-colors hover:border-border-strong"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-text">{v.company_name}</p>
              <p className="truncate text-xs text-muted">
                {v.specialization ?? "—"} · {v.region}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              {v.bnef_tier === 1 && <Badge variant="success">Tier 1</Badge>}
              {v.bnef_tier != null && v.bnef_tier > 1 && <Badge variant="warning">Tier {v.bnef_tier}</Badge>}
              <span className="text-xs tabular-nums text-muted">{formatPct(v.on_time_rate)}</span>
            </div>
          </button>
        ))}
        {vendors.length === 0 && <p className="py-4 text-center text-xs text-muted">No matching vendors.</p>}
      </CardBody>
    </Card>
  );
}
