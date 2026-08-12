import { useEffect, useState } from "react";
import ProgressBar from "../components/ProgressBar";
import { api, formatMYR, type AnalyticsOverview, type Vendor } from "../lib/api";

export default function Vendors() {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);

  useEffect(() => {
    api.listVendors().then(setVendors);
    api.getAnalytics().then(setAnalytics);
  }, []);

  const spendByVendor = new Map(analytics?.vendor_leaderboard.map((v) => [v.vendor_id, v]) ?? []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900">Vendors</h1>
      <p className="mt-1 text-sm text-gray-500">Approved suppliers across all regions, ranked by spend and reliability.</p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {vendors.map((vendor) => {
          const entry = spendByVendor.get(vendor.id);
          return (
            <div key={vendor.id} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">{vendor.company_name}</h2>
                  <p className="text-sm text-gray-500">{vendor.specialization}</p>
                </div>
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium capitalize text-gray-600">
                  {vendor.region}
                </span>
              </div>

              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>On-time delivery</span>
                  <span className="font-medium text-gray-900">{vendor.on_time_rate}%</span>
                </div>
                <ProgressBar
                  pct={vendor.on_time_rate ?? 0}
                  colorClass={(vendor.on_time_rate ?? 0) >= 95 ? "bg-green-600" : (vendor.on_time_rate ?? 0) >= 90 ? "bg-yellow-500" : "bg-orange-500"}
                />
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-3 text-sm">
                <div>
                  <p className="text-gray-500">Orders placed</p>
                  <p className="font-medium text-gray-900">{entry?.total_orders ?? 0}</p>
                </div>
                <div className="text-right">
                  <p className="text-gray-500">Total spend</p>
                  <p className="font-medium text-gray-900">{formatMYR(entry?.total_spend ?? 0)}</p>
                </div>
              </div>

              <p className="mt-3 truncate text-xs text-gray-400">{vendor.contact_email}</p>
            </div>
          );
        })}
        {vendors.length === 0 && <p className="text-sm text-gray-400">No vendors found.</p>}
      </div>
    </div>
  );
}
