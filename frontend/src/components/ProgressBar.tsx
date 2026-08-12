export default function ProgressBar({ pct, colorClass = "bg-green-600" }: { pct: number; colorClass?: string }) {
  const clamped = Math.min(100, Math.max(0, pct));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
      <div className={`h-2 rounded-full ${colorClass} transition-all`} style={{ width: `${clamped}%` }} />
    </div>
  );
}
