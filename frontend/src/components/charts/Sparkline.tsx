import { motion, useReducedMotion } from "motion/react";
import { useId, useMemo } from "react";
import { cn } from "../../lib/cn";
import { fillClass, strokeClass, textClass, type ChartTone } from "./tones";
import { buildSmoothPath, scaleLinear } from "./utils";

export type { ChartTone };

export interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  tone?: ChartTone;
  strokeWidth?: number;
  fill?: boolean;
  className?: string;
  ariaLabel: string;
}

/** Tiny axis-less trend line for KPI tiles. Renders gracefully with 0, 1, or many points. */
export function Sparkline({ data, width = 96, height = 28, tone = "chart-1", strokeWidth = 1.75, fill = true, className, ariaLabel }: SparklineProps) {
  const gradientId = useId();
  const reduceMotion = useReducedMotion();
  const pad = strokeWidth;

  const path = useMemo(() => {
    if (data.length === 0) return null;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const yScale = scaleLinear([min, max], [height - pad, pad]);
    const xScale = scaleLinear([0, Math.max(1, data.length - 1)], [pad, width - pad]);

    if (data.length === 1) {
      const x = width / 2;
      const y = yScale(data[0]);
      return { line: `M ${x} ${y}`, area: "", points: [{ x, y }] };
    }

    const points = data.map((v, i) => ({ x: xScale(i), y: yScale(v) }));
    const line = buildSmoothPath(points);
    const area = `${line} L ${points[points.length - 1].x} ${height} L ${points[0].x} ${height} Z`;
    return { line, area, points };
  }, [data, width, height, pad]);

  const summary = data.length === 0 ? "No data" : `${data.length} points, from ${Math.min(...data).toLocaleString()} to ${Math.max(...data).toLocaleString()}`;

  if (!path) {
    return (
      <div role="img" aria-label={`${ariaLabel}: no data`} className={cn("flex items-center", className)} style={{ width, height }}>
        <div className="h-px w-full bg-border" />
      </div>
    );
  }

  return (
    <svg
      role="img"
      aria-label={`${ariaLabel}. ${summary}.`}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
    >
      {fill && data.length > 1 && (
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" className={textClass[tone]} style={{ stopColor: "currentColor", stopOpacity: 0.3 }} />
            <stop offset="100%" className={textClass[tone]} style={{ stopColor: "currentColor", stopOpacity: 0 }} />
          </linearGradient>
        </defs>
      )}
      {fill && path.area && <path d={path.area} fill={`url(#${gradientId})`} stroke="none" />}
      {data.length === 1 ? (
        <circle cx={path.points[0].x} cy={path.points[0].y} r={strokeWidth * 1.4} className={fillClass[tone]} />
      ) : (
        <motion.path
          d={path.line}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
          className={strokeClass[tone]}
          initial={reduceMotion ? undefined : { pathLength: 0 }}
          animate={reduceMotion ? undefined : { pathLength: 1 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        />
      )}
    </svg>
  );
}
