import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export type BadgeVariant = "neutral" | "success" | "warning" | "danger" | "info";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  /** Renders a small status dot before the label instead of a filled pill. */
  dot?: boolean;
}

const fillClasses: Record<BadgeVariant, string> = {
  neutral: "bg-bg-subtle text-muted border-border",
  success: "bg-success/15 text-success border-success/30",
  warning: "bg-warning/15 text-warning border-warning/30",
  danger: "bg-danger/15 text-danger border-danger/30",
  info: "bg-info/15 text-info border-info/30",
};

const dotClasses: Record<BadgeVariant, string> = {
  neutral: "bg-subtle",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
};

export function Badge({ variant = "neutral", dot = false, className, children, ...props }: BadgeProps) {
  if (dot) {
    return (
      <span
        className={cn("inline-flex items-center gap-1.5 text-xs font-medium text-muted", className)}
        {...props}
      >
        <span className={cn("size-1.5 rounded-full", dotClasses[variant])} aria-hidden="true" />
        {children}
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        fillClasses[variant],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
