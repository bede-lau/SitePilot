import type { ActivityEvent } from "../hooks/useActivityFeed";

function iconFor(entityType: string | null): string {
  switch (entityType) {
    case "inspection_report":
      return "\u{1F4F7}"; // camera
    case "invoice_draft":
      return "\u{1F4C4}"; // page
    case "purchase_order":
      return "\u{1F4E6}"; // package
    default:
      return "\u{2728}";
  }
}

function relativeTime(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

export default function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-gray-400">No activity yet. Send a Telegram message to FieldBot to get started.</p>;
  }

  return (
    <ul className="space-y-2">
      {events.map((event, idx) => (
        <li
          key={event.id}
          className={`flex items-start gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm ${
            idx === 0 ? "animate-slide-in ring-1 ring-green-300" : ""
          }`}
        >
          <span className="text-xl">{iconFor(event.entity_type)}</span>
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-900">{event.description}</p>
            <p className="text-xs text-gray-400">{relativeTime(event.timestamp)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
