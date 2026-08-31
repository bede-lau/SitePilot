import { Badge, Card, CardBody, CardHeader, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../ui";
import { formatMYR } from "../../lib/format";
import type { BadgeVariant } from "../ui";

/**
 * The RFQ batch response isn't part of the frozen ARD §5.3/§5.4 contract, so this reads its shape
 * defensively — a batch of per-vendor rows keyed a couple of plausible ways — and renders an
 * em-dash for anything absent rather than guessing.
 */
interface RfqRow {
  company_name?: string;
  vendor_name?: string;
  status?: string;
  quote_price_myr?: number | null;
  quoted_price_myr?: number | null;
  quote_lead_time_days?: number | null;
}

interface RfqStatusPayload {
  item?: string;
  quantity?: number;
  status?: string;
  quotes?: RfqRow[];
  rfqs?: RfqRow[];
}

function statusTone(status: string | undefined): BadgeVariant {
  if (status === "quoted") return "success";
  if (status === "declined" || status === "expired") return "danger";
  return "info";
}

export function RfqStatusCard({ data }: { data: unknown }) {
  const payload = (data ?? {}) as RfqStatusPayload;
  const rows = payload.quotes ?? payload.rfqs ?? [];

  return (
    <Card elevation="sm">
      <CardHeader>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text">RFQ batch{payload.item ? ` — ${payload.item}` : ""}</p>
          {payload.quantity !== undefined && <p className="text-xs text-muted">Qty {payload.quantity}</p>}
        </div>
        {payload.status && <Badge variant={statusTone(payload.status)}>{payload.status}</Badge>}
      </CardHeader>
      <CardBody className="p-0">
        <Table>
          <TableHead>
            <tr>
              <TableHeaderCell>Vendor</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Quote</TableHeaderCell>
              <TableHeaderCell>Lead time</TableHeaderCell>
            </tr>
          </TableHead>
          <TableBody>
            {rows.map((r, i) => (
              <TableRow key={i}>
                <TableCell>{r.company_name ?? r.vendor_name ?? "—"}</TableCell>
                <TableCell>
                  <Badge variant={statusTone(r.status)}>{r.status ?? "—"}</Badge>
                </TableCell>
                <TableCell className="tabular-nums">{formatMYR(r.quote_price_myr ?? r.quoted_price_myr)}</TableCell>
                <TableCell className="tabular-nums">{r.quote_lead_time_days != null ? `${r.quote_lead_time_days}d` : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {rows.length === 0 && <p className="px-4 py-6 text-center text-xs text-muted">No vendor responses yet.</p>}
      </CardBody>
    </Card>
  );
}
