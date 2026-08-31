import { cn } from "../../lib/cn";

export type ProgressTone = "accent" | "success" | "warning" | "danger" | "info";

export interface ProgressProps {
  /** 0-100. Ignored (shows an animated indeterminate bar) when `indeterminate` is true. */
  value?: number;
  tone?: ProgressTone;
  className?: string;
  label?: string;
  /** Shows the numeric percentage to the right of the bar. */
  showValue?: boolean;
}

const toneClasses: Record<ProgressTone, string> = {
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
};

export function Progress({ value = 0, tone = "accent", className, label, showValue = false }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div className={cn("w-full", className)}>
      {(label || showValue) && (
        <div className="mb-1.5 flex items-center justify-between text-xs text-muted">
          {label && <span>{label}</span>}
          {showValue && <span className="tabular-nums font-medium text-text">{Math.round(clamped)}%</span>}
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={!label ? "Progress" : undefined}
        className="h-1.5 w-full overflow-hidden rounded-full bg-bg-subtle"
      >
        <div
          className={cn("h-full rounded-full transition-[width] duration-[320ms] ease-out", toneClasses[tone])}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

export interface IndeterminateProgressProps {
  tone?: ProgressTone;
  className?: string;
}

/** A thin, looping bar for actions with no known duration (e.g. "Reading page 2 of 3…"). */
export function IndeterminateProgress({ tone = "accent", className }: IndeterminateProgressProps) {
  return (
    <div className={cn("h-1 w-full overflow-hidden rounded-full bg-bg-subtle", className)}>
      <div className={cn("h-full w-1/3 rounded-full motion-safe:animate-indeterminate", toneClasses[tone])} />
    </div>
  );
}
