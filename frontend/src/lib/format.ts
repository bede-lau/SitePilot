/**
 * Centralized number/unit formatting. Every metric in the UI should go through one of these
 * so rounding is consistent instead of scattered `toFixed` calls. Formatters never invent data —
 * callers pass `null`/`undefined` through and the formatter renders an em-dash.
 */

const EM_DASH = "—";

export function formatMYR(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return EM_DASH;
  return `RM ${Math.round(amount).toLocaleString("en-MY")}`;
}

export function formatKwh(value: number | null | undefined, opts: { decimals?: number } = {}): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  const decimals = opts.decimals ?? (Math.abs(value) < 100 ? 1 : 0);
  return `${value.toLocaleString("en-MY", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })} kWh`;
}

export function formatKwp(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toLocaleString("en-MY", { minimumFractionDigits: 1, maximumFractionDigits: 2 })} kWp`;
}

export function formatPct(value: number | null | undefined, opts: { decimals?: number } = {}): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  const decimals = opts.decimals ?? 0;
  return `${value.toLocaleString("en-MY", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}%`;
}

export function formatVolts(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toLocaleString("en-MY", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} V`;
}

export function formatAmps(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toLocaleString("en-MY", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} A`;
}

export function formatYearRange(range: [number, number] | null | undefined): string {
  if (!range) return EM_DASH;
  const [lo, hi] = range;
  const fmt = (n: number) => n.toLocaleString("en-MY", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${fmt(lo)}–${fmt(hi)} yrs`;
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return EM_DASH;
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (Number.isNaN(seconds)) return EM_DASH;
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-MY", { day: "numeric", month: "short", year: "numeric" });
}

export function formatNumber(value: number | null | undefined, opts: { decimals?: number } = {}): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  const decimals = opts.decimals ?? 0;
  return value.toLocaleString("en-MY", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
