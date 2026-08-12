export interface BarDatum {
  label: string;
  value: number;
}

export default function BarChart({
  data,
  formatValue = (v) => String(v),
  color = "bg-green-600",
}: {
  data: BarDatum[];
  formatValue?: (v: number) => string;
  color?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));

  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3 text-sm">
          <span className="w-28 shrink-0 truncate text-gray-500">{d.label}</span>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100">
            <div
              className={`h-2.5 rounded-full ${color} transition-all`}
              style={{ width: `${Math.max(2, (d.value / max) * 100)}%` }}
            />
          </div>
          <span className="w-20 shrink-0 text-right font-medium text-gray-900">{formatValue(d.value)}</span>
        </div>
      ))}
      {data.length === 0 && <p className="text-sm text-gray-400">No data yet.</p>}
    </div>
  );
}
