import { useEffect, useMemo, useState } from "react";
import { Badge, Card, CardBody, EmptyState, Skeleton, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui";
import { api, formatMYR, type Project, type PurchaseOrder, type Vendor } from "../lib/api";
import { cn } from "../lib/cn";

function statusVariant(s: string): "success" | "info" | "warning" {
  if (s === "delivered") return "success";
  if (s === "approved") return "info";
  return "warning";
}

export default function PurchaseOrdersList() {
  const [pos, setPos] = useState<PurchaseOrder[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [status, setStatus] = useState("all");

  useEffect(() => {
    api
      .listPurchaseOrders()
      .then(setPos)
      .catch(() => setPos([]));
    api.listProjects().then(setProjects).catch(() => {});
    api.listVendors().then(setVendors).catch(() => {});
  }, []);

  const projectName = (id: number) => projects.find((p) => p.id === id)?.name ?? `Project ${id}`;
  const vendorName = (id: number) => vendors.find((v) => v.id === id)?.company_name ?? `Vendor ${id}`;

  const filtered = useMemo(() => (status === "all" ? (pos ?? []) : (pos ?? []).filter((p) => p.status === status)), [pos, status]);
  const totalSpend = useMemo(() => filtered.reduce((sum, p) => sum + (p.total_price_myr ?? 0), 0), [filtered]);
  const statuses = useMemo(() => Array.from(new Set((pos ?? []).map((p) => p.status))).sort(), [pos]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight text-text">Purchase Orders</h1>
        <p className="text-sm text-muted">
          {filtered.length} orders · {formatMYR(totalSpend)} total
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setStatus("all")}
          className={cn("rounded-full px-3 py-1 text-sm font-medium transition-colors", status === "all" ? "bg-accent text-accent-fg" : "bg-bg-subtle text-muted hover:text-text")}
        >
          All
        </button>
        {statuses.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setStatus(s)}
            className={cn("rounded-full px-3 py-1 text-sm font-medium capitalize transition-colors", status === s ? "bg-accent text-accent-fg" : "bg-bg-subtle text-muted hover:text-text")}
          >
            {s}
          </button>
        ))}
      </div>

      {!pos ? (
        <Skeleton variant="rect" height={320} />
      ) : filtered.length === 0 ? (
        <EmptyState title="No purchase orders" body="Approved POs from the feasibility workbench or chat will appear here." />
      ) : (
        <Card elevation="sm">
          <CardBody className="p-0">
            <Table>
              <TableHead>
                <tr>
                  <TableHeaderCell>PO Number</TableHeaderCell>
                  <TableHeaderCell>Project</TableHeaderCell>
                  <TableHeaderCell>Vendor</TableHeaderCell>
                  <TableHeaderCell>Item</TableHeaderCell>
                  <TableHeaderCell>Qty</TableHeaderCell>
                  <TableHeaderCell>Total</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Date</TableHeaderCell>
                </tr>
              </TableHead>
              <TableBody>
                {filtered.map((po) => (
                  <TableRow key={po.id}>
                    <TableCell className="font-medium text-text">{po.po_number}</TableCell>
                    <TableCell>{projectName(po.project_id)}</TableCell>
                    <TableCell>{vendorName(po.vendor_id)}</TableCell>
                    <TableCell>{po.item_description}</TableCell>
                    <TableCell className="tabular-nums">{po.quantity}</TableCell>
                    <TableCell className="tabular-nums">{formatMYR(po.total_price_myr)}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(po.status)}>{po.status}</Badge>
                    </TableCell>
                    <TableCell className="text-muted">{new Date(po.created_at).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
