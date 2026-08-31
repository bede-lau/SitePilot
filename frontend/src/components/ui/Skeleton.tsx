import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export type SkeletonVariant = "text" | "circle" | "rect";

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  variant?: SkeletonVariant;
  width?: number | string;
  height?: number | string;
}

const variantClasses: Record<SkeletonVariant, string> = {
  text: "rounded-sm",
  circle: "rounded-full",
  rect: "rounded-md",
};

/**
 * Shimmer respects `prefers-reduced-motion` globally (index.css freezes all animation durations
 * under that media query) so this degrades to a static tone instead of a moving gradient.
 */
export function Skeleton({ variant = "rect", width, height, className, style, ...props }: SkeletonProps) {
  return (
    <div
      role="presentation"
      aria-hidden="true"
      className={cn(
        "animate-shimmer bg-[linear-gradient(90deg,var(--bg-subtle)_25%,var(--surface-hover)_50%,var(--bg-subtle)_75%)] bg-[length:200%_100%]",
        variantClasses[variant],
        variant === "text" && !height && "h-4",
        className,
      )}
      style={{ width, height, ...style }}
      {...props}
    />
  );
}

/** A skeleton row shaped like a stat tile — for KPI rails during the first data fetch. */
export function SkeletonStatCard() {
  return (
    <div className="rounded-lg border border-border bg-surface p-5">
      <Skeleton variant="text" width="60%" height={12} />
      <Skeleton variant="text" width="40%" height={28} className="mt-3" />
    </div>
  );
}

/** A skeleton shaped like a chat message bubble pair, for the initial history load. */
export function SkeletonChatMessage({ align = "start" }: { align?: "start" | "end" }) {
  return (
    <div className={cn("flex flex-col gap-2", align === "end" ? "items-end" : "items-start")}>
      <Skeleton variant="text" width={align === "end" ? 180 : 260} height={14} />
      <Skeleton variant="text" width={align === "end" ? 120 : 200} height={14} />
    </div>
  );
}
