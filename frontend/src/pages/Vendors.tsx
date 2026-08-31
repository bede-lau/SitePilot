import { useEffect, useState } from "react";
import { Badge, Card, CardBody, EmptyState, Progress, Skeleton, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui";
import { api, formatMYR, type AnalyticsOverview, type Vendor } from "../lib/api";

/** Restyled onto the design system, with BNEF tier + brands-carried columns (ARD §6.3). */
export default function Vendors() {
  const [vendors, setVendors] = useState<Vendor[] | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);

  useEffect(() => {
    api
      .listVendors()
      .then(setVendors)
      .catch(() => setVendors([]));
    api.getAnalytics().then(setAnalytics).catch(() => {});
  }, []);

  const spendByVendor = new Map(analytics?.vendor_leaderboard.map((v) => [v.vendor_id, v]) ?? []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text">Vendors</h1>
        <p className="mt-1 text-sm text-muted">Approved suppliers across all regions, ranked by spend and reliability.</p>
      </div>

      {!vendors ? (
        <Skeleton variant="rect" height={320} />
      ) : vendors.length === 0 ? (
        <EmptyState title="No vendors found" body="Vendors seeded from the backend will appear here." />
      ) : (
        <Card elevation="sm">
          <CardBody className="p-0">
            <Table>
              <TableHead>
                <tr>
                  <TableHeaderCell>Company</TableHeaderCell>
                  <TableHeaderCell>Region</TableHeaderCell>
                  <TableHeaderCell>BNEF tier</TableHeaderCell>
                  <TableHeaderCell>Brands carried</TableHeaderCell>
                  <TableHeaderCell>On-time rate</TableHeaderCell>
                  <TableHeaderCell>Orders</TableHeaderCell>
                  <TableHeaderCell>Total spend</TableHeaderCell>
                </tr>
              </TableHead>
              <TableBody>
                {vendors.map((vendor) => {
                  const entry = spendByVendor.get(vendor.id);
                  return (
                    <TableRow key={vendor.id}>
                      <TableCell>
                        <p className="font-medium text-text">{vendor.company_name}</p>
                        <p className="text-xs text-muted">{vendor.specialization ?? "—"}</p>
                      </TableCell>
                      <TableCell className="capitalize">{vendor.region}</TableCell>
                      <TableCell>
                        {vendor.bnef_tier === 1 && <Badge variant="success">Tier 1</Badge>}
                        {vendor.bnef_tier != null && vendor.bnef_tier > 1 && <Badge variant="warning">Tier {vendor.bnef_tier}</Badge>}
                        {vendor.bnef_tier == null && <span className="text-subtle">—</span>}
                      </TableCell>
                      <TableCell>
                        <div className="flex max-w-[220px] flex-wrap gap-1">
                          {(vendor.brands_carried ?? []).length === 0 && <span className="text-subtle">—</span>}
                          {(vendor.brands_carried ?? []).map((b) => (
                            <Badge key={b} variant="neutral">
                              {b}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="w-32">
                        <Progress value={vendor.on_time_rate ?? 0} tone={(vendor.on_time_rate ?? 0) >= 95 ? "success" : (vendor.on_time_rate ?? 0) >= 90 ? "warning" : "danger"} showValue />
                      </TableCell>
                      <TableCell className="tabular-nums">{entry?.total_orders ?? 0}</TableCell>
                      <TableCell className="tabular-nums">{formatMYR(entry?.total_spend ?? 0)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
