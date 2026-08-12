import { useEffect, useMemo, useState } from "react";
import { api, formatMYR, type Project, type PurchaseOrder, type Vendor } from "../lib/api";

export default function PurchaseOrdersList() {
  const [pos, setPos] = useState<PurchaseOrder[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [status, setStatus] = useState("all");

  useEffect(() => {
    api.listPurchaseOrders().then(setPos);
    api.listProjects().then(setProjects);
    api.listVendors().then(setVendors);
  }, []);

  const projectName = (id: number) => projects.find((p) => p.id === id)?.name ?? `Project ${id}`;
  const vendorName = (id: number) => vendors.find((v) => v.id === id)?.company_name ?? `Vendor ${id}`;

  const filtered = useMemo(() => (status === "all" ? pos : pos.filter((p) => p.status === status)), [pos, status]);
  const totalSpend = useMemo(() => filtered.reduce((sum, p) => sum + (p.total_price_myr ?? 0), 0), [filtered]);
  const statuses = useMemo(() => Array.from(new Set(pos.map((p) => p.status))).sort(), [pos]);

  const statusStyle = (s: string) =>
    s === "delivered"
      ? "bg-green-100 text-green-700"
      : s === "approved"
        ? "bg-blue-100 text-blue-700"
        : "bg-yellow-100 text-yellow-700";

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Purchase Orders</h1>
        <p className="text-sm text-gray-500">
          {filtered.length} orders · {formatMYR(totalSpend)} total
        </p>
      </div>

      <div className="mt-4 flex gap-2">
        <button
          onClick={() => setStatus("all")}
          className={`rounded-full px-3 py-1 text-sm font-medium ${
            status === "all" ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          All
        </button>
        {statuses.map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={`rounded-full px-3 py-1 text-sm font-medium capitalize ${
              status === s ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-gray-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-gray-500">
            <tr>
              <th className="px-4 py-3 font-medium">PO Number</th>
              <th className="px-4 py-3 font-medium">Project</th>
              <th className="px-4 py-3 font-medium">Vendor</th>
              <th className="px-4 py-3 font-medium">Item</th>
              <th className="px-4 py-3 font-medium">Qty</th>
              <th className="px-4 py-3 font-medium">Total</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Date</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((po) => (
              <tr key={po.id} className="border-t border-gray-100">
                <td className="px-4 py-3 font-medium text-gray-900">{po.po_number}</td>
                <td className="px-4 py-3 text-gray-600">{projectName(po.project_id)}</td>
                <td className="px-4 py-3 text-gray-600">{vendorName(po.vendor_id)}</td>
                <td className="px-4 py-3 text-gray-600">{po.item_description}</td>
                <td className="px-4 py-3 text-gray-600">{po.quantity}</td>
                <td className="px-4 py-3 text-gray-900">{formatMYR(po.total_price_myr)}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${statusStyle(po.status)}`}>
                    {po.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">{new Date(po.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <p className="px-4 py-6 text-sm text-gray-400">No purchase orders match this filter.</p>}
      </div>
    </div>
  );
}
