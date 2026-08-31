import { Camera, FileText, Package, Sparkles } from "lucide-react";
import { cn } from "../lib/cn";
import { formatRelativeTime } from "../lib/format";
import type { ActivityEvent } from "../hooks/useActivityFeed";

function iconFor(entityType: string | null) {
  switch (entityType) {
    case "inspection_report":
      return Camera;
    case "invoice_draft":
      return FileText;
    case "purchase_order":
      return Package;
    default:
      return Sparkles;
  }
}

export default function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-muted">No activity yet. Send a Telegram message to FieldBot to get started.</p>;
  }

  return (
    <ul className="space-y-2">
      {events.map((event, idx) => {
        const Icon = iconFor(event.entity_type);
        return (
          <li
            key={event.id}
            className={cn(
              "flex items-start gap-3 rounded-lg border border-border bg-surface px-3.5 py-2.5",
              idx === 0 && "motion-safe:animate-slide-in ring-1 ring-accent/40",
            )}
          >
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent/12 text-accent">
              <Icon className="size-3.5" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-text">{event.description}</p>
              <p className="text-xs text-subtle">{formatRelativeTime(event.timestamp)}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
