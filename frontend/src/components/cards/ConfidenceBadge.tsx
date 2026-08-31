import { Info } from "lucide-react";
import { useState } from "react";
import { cn } from "../../lib/cn";
import { RadialGauge } from "../charts";
import type { ChartTone } from "../charts";
import { Badge } from "../ui";
import type { ConfidenceScore } from "../../lib/types";

export interface ConfidenceBadgeProps {
  confidence: ConfidenceScore;
  size?: "sm" | "md";
  className?: string;
}

/** Hard guardrail (PRD §4.5): never display a score above 94, no matter what the API sends. */
const MAX_DISPLAY_SCORE = 94;

function bandTone(score: number): ChartTone {
  if (score >= 90) return "success";
  if (score >= 85) return "accent";
  if (score >= 70) return "warning";
  return "danger";
}

/** Radial gauge + band label + a breakdown popover of each scoring component's delta. The
 * "AI-estimated, installer-confirmed" disclaimer is always rendered directly beside the score —
 * never gated behind the popover — per ARD §6.5 non-negotiable #7. */
export function ConfidenceBadge({ confidence, size = "md", className }: ConfidenceBadgeProps) {
  const [open, setOpen] = useState(false);
  const score = Math.min(MAX_DISPLAY_SCORE, confidence.score);
  const tone = bandTone(score);
  const gaugeSize = size === "sm" ? 92 : 132;

  return (
    <div className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 rounded-lg border border-border bg-surface p-3 text-left transition-colors hover:border-border-strong"
        aria-expanded={open}
      >
        <RadialGauge
          value={score}
          tone={tone}
          size={gaugeSize}
          strokeWidth={size === "sm" ? 8 : 11}
          ariaLabel="Confidence score"
          bands={[
            { from: 0, to: 70, tone: "danger" },
            { from: 70, to: 85, tone: "warning" },
            { from: 85, to: 90, tone: "accent" },
            { from: 90, to: 94, tone: "success" },
          ]}
          centerLabel={
            <>
              <span className="text-2xl font-semibold tabular-nums text-text">{Math.round(score)}</span>
              <span className="text-[10px] text-subtle">/ 100</span>
            </>
          }
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-text">{confidence.band}</p>
          <p className="mt-0.5 flex items-start gap-1 text-[11px] text-muted">
            <Info className="mt-px size-3 shrink-0" aria-hidden="true" />
            {confidence.disclaimer}
          </p>
          <Badge variant="neutral" className="mt-1.5">
            {open ? "Hide breakdown" : "Show breakdown"}
          </Badge>
        </div>
      </button>

      {open && (
        <div className="mt-2 space-y-1.5 rounded-lg border border-border bg-bg-subtle p-3">
          {confidence.components.map((c, i) => (
            <div key={i} className="flex items-start justify-between gap-3 text-xs">
              <div className="min-w-0">
                <p className={cn("truncate", c.applied ? "text-text" : "text-subtle line-through")}>{c.label}</p>
                <p className="text-[10px] text-subtle">{c.reason}</p>
              </div>
              <span className={cn("shrink-0 tabular-nums font-medium", c.applied ? (c.delta >= 0 ? "text-success" : "text-danger") : "text-subtle")}>
                {c.applied ? (c.delta >= 0 ? `+${c.delta}` : c.delta) : "—"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
