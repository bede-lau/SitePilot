import { motion, useReducedMotion } from "motion/react";
import { cn } from "../../lib/cn";
import { fillClass } from "./tones";
import { scaleLinear, useElementSize } from "./utils";

export interface RangeMeterProps {
  value: number;
  min: number;
  max: number;
  bandMin: number;
  bandMax: number;
  valueFormatter?: (value: number) => string;
  label?: string;
  height?: number;
  ariaLabel: string;
  className?: string;
}

const TRACK_H = 8;

/** Plots a value on a track against a "pass band" — e.g. DC:AC ratio inside the 1.2–1.5x window. */
export function RangeMeter({ value, min, max, bandMin, bandMax, valueFormatter = String, label, height = 52, ariaLabel, className }: RangeMeterProps) {
  const [containerRef, size] = useElementSize<HTMLDivElement>();
  const reduceMotion = useReducedMotion();
  const width = size.width;

  const inBand = value >= bandMin && value <= bandMax;
  const tone = inBand ? "success" : "danger";

  const xScale = scaleLinear([min, max], [0, width]);
  const clampedValueX = Math.min(width, Math.max(0, xScale(value)));

  return (
    <div ref={containerRef} className={cn("w-full", className)}>
      <div className="mb-1.5 flex items-center justify-between text-xs">
        {label && <span className="text-muted">{label}</span>}
        <span className={cn("font-medium tabular-nums", inBand ? "text-success" : "text-danger")}>{valueFormatter(value)}</span>
      </div>
      <div role="img" aria-label={`${ariaLabel}: ${valueFormatter(value)}, pass range ${valueFormatter(bandMin)}–${valueFormatter(bandMax)}, ${inBand ? "within range" : "out of range"}.`} style={{ height: height - 20 }}>
        {width > 0 && (
          <svg width={width} height={height - 20} viewBox={`0 0 ${width} ${height - 20}`} className="overflow-visible">
            <rect x={0} y={(height - 20) / 2 - TRACK_H / 2} width={width} height={TRACK_H} rx={TRACK_H / 2} className="fill-bg-subtle" />
            <rect
              x={xScale(bandMin)}
              y={(height - 20) / 2 - TRACK_H / 2}
              width={Math.max(0, xScale(bandMax) - xScale(bandMin))}
              height={TRACK_H}
              rx={TRACK_H / 2}
              className="fill-success"
              opacity={0.25}
            />
            <line x1={xScale(bandMin)} x2={xScale(bandMin)} y1={2} y2={height - 22} className="stroke-success" strokeWidth={1} strokeDasharray="2 2" opacity={0.6} />
            <line x1={xScale(bandMax)} x2={xScale(bandMax)} y1={2} y2={height - 22} className="stroke-success" strokeWidth={1} strokeDasharray="2 2" opacity={0.6} />

            <motion.circle
              cx={clampedValueX}
              cy={(height - 20) / 2}
              r={7}
              className={fillClass[tone]}
              stroke="var(--bg-elevated)"
              strokeWidth={2.5}
              initial={reduceMotion ? undefined : { scale: 0 }}
              animate={reduceMotion ? undefined : { scale: 1 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
              style={{ transformOrigin: `${clampedValueX}px ${(height - 20) / 2}px` }}
            />
          </svg>
        )}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-subtle">
        <span>{valueFormatter(min)}</span>
        <span className="text-success">
          pass: {valueFormatter(bandMin)}–{valueFormatter(bandMax)}
        </span>
        <span>{valueFormatter(max)}</span>
      </div>
    </div>
  );
}
