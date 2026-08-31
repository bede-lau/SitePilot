import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import { strokeClass, type ChartTone } from "./tones";
import { describeArc, scaleLinear } from "./utils";

export interface RadialGaugeBand {
  from: number;
  to: number;
  tone: ChartTone;
}

export interface RadialGaugeProps {
  value: number;
  min?: number;
  max?: number;
  /** Background zone coloring, e.g. confidence bands (ARD §4.9). Value arc color follows the active band. */
  bands?: RadialGaugeBand[];
  tone?: ChartTone;
  size?: number;
  strokeWidth?: number;
  centerLabel?: ReactNode;
  ariaLabel: string;
  className?: string;
}

const START_ANGLE = -120;
const END_ANGLE = 120;

/** A 240° arc gauge (60° gap at the bottom) — used for the confidence score, reusable for any 0..max metric. */
export function RadialGauge({
  value,
  min = 0,
  max = 100,
  bands,
  tone = "accent",
  size = 160,
  strokeWidth = 12,
  centerLabel,
  ariaLabel,
  className,
}: RadialGaugeProps) {
  const reduceMotion = useReducedMotion();
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - strokeWidth;

  const angleScale = scaleLinear([min, max], [START_ANGLE, END_ANGLE]);
  const clamped = Math.min(max, Math.max(min, value));
  const valueAngle = angleScale(clamped);

  const trackPath = describeArc(cx, cy, radius, START_ANGLE, END_ANGLE);
  const valuePath = describeArc(cx, cy, radius, START_ANGLE, valueAngle);
  const activeTone = bands?.find((b) => clamped >= b.from && clamped <= b.to)?.tone ?? tone;

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${ariaLabel}: ${Math.round(clamped)} of ${max}`}>
        <path d={trackPath} fill="none" stroke="var(--bg-subtle)" strokeWidth={strokeWidth} strokeLinecap="round" />

        {bands?.map((band) => (
          <path
            key={`${band.from}-${band.to}`}
            d={describeArc(cx, cy, radius, angleScale(Math.max(min, band.from)), angleScale(Math.min(max, band.to)))}
            fill="none"
            className={strokeClass[band.tone]}
            strokeWidth={strokeWidth}
            opacity={0.22}
          />
        ))}

        <motion.path
          d={valuePath}
          fill="none"
          className={strokeClass[activeTone]}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          initial={reduceMotion ? undefined : { pathLength: 0 }}
          animate={reduceMotion ? undefined : { pathLength: 1 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      {centerLabel && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">{centerLabel}</div>
      )}
    </div>
  );
}
