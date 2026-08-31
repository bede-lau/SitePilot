import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  body?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, body, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 px-6 py-12 text-center", className)}>
      {icon && (
        <div className="flex size-12 items-center justify-center rounded-full bg-bg-subtle text-subtle [&_svg]:size-6">
          {icon}
        </div>
      )}
      <div className="space-y-1">
        <p className="text-sm font-medium text-text">{title}</p>
        {body && <p className="max-w-sm text-sm text-muted">{body}</p>}
      </div>
      {action}
    </div>
  );
}
