import { motion, useReducedMotion } from "motion/react";
import { useId, useMemo, useState } from "react";
import { cn } from "../../lib/cn";
import { fillClass, strokeClass, textClass, type ChartTone } from "./tones";
import { buildSmoothPath, scaleLinear, useElementSize } from "./utils";

export interface AreaChartPoint {
  label: string;
  value: number;
}

export interface AreaChartProps {
  data: AreaChartPoint[];
  height?: number;
  tone?: ChartTone;
  valueFormatter?: (value: number) => string;
  ariaLabel: string;
  className?: string;
}

const PAD = { top: 16, right: 16, bottom: 10, left: 16 };
const GRIDLINES = 3;

export function AreaChart({ data, height = 220, tone = "chart-1", valueFormatter = String, ariaLabel, className }: AreaChartProps) {
  const [containerRef, size] = useElementSize<HTMLDivElement>();
  const gradientId = useId();
  const reduceMotion = useReducedMotion();
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const width = size.width;
  const innerW = Math.max(0, width - PAD.left - PAD.right);
  const innerH = Math.max(0, height - PAD.top - PAD.bottom);

  const layout = useMemo(() => {
    if (data.length === 0 || width === 0) return null;

    const values = data.map((d) => d.value);
    const maxValue = Math.max(...values, 0);
    const minValue = Math.min(...values, 0);
    const domainMax = maxValue === 0 && minValue === 0 ? 1 : maxValue + (maxValue - minValue) * 0.12;
    const yScale = scaleLinear([minValue, domainMax], [PAD.top + innerH, PAD.top]);
    const xScale = scaleLinear([0, Math.max(1, data.length - 1)], [PAD.left, PAD.left + innerW]);

    const points = data.map((d, i) => ({
      x: data.length === 1 ? PAD.left + innerW / 2 : xScale(i),
      y: yScale(d.value),
    }));

    const linePath = buildSmoothPath(points);
    const baselineY = yScale(Math.max(0, minValue));
    const areaPath = points.length > 1 ? `${linePath} L ${points[points.length - 1].x} ${baselineY} L ${points[0].x} ${baselineY} Z` : "";

    const gridY = Array.from({ length: GRIDLINES + 1 }, (_, i) => {
      const value = minValue + ((domainMax - minValue) * i) / GRIDLINES;
      return { y: yScale(value), value };
    });

    return { points, linePath, areaPath, gridY, maxValue, minValue };
  }, [data, width, innerW, innerH]);

  const summary =
    data.length === 0
      ? "No data"
      : `${data.length} points from ${data[0].label} to ${data[data.length - 1].label}, ranging ${valueFormatter(layout?.minValue ?? 0)} to ${valueFormatter(layout?.maxValue ?? 0)}`;

  function onMove(e: React.MouseEvent<SVGRectElement>) {
    if (!layout || layout.points.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    let nearest = 0;
    let nearestDist = Infinity;
    layout.points.forEach((p, i) => {
      const dist = Math.abs(p.x - mouseX);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearest = i;
      }
    });
    setActiveIndex(nearest);
  }

  const active = activeIndex !== null ? layout?.points[activeIndex] : null;
  const activeDatum = activeIndex !== null ? data[activeIndex] : null;
  const tooltipLeft = active ? Math.min(Math.max(active.x, 56), width - 56) : 0;
  const tooltipAlignRight = active ? active.x > width - 90 : false;

  return (
    <div
      ref={containerRef}
      className={cn("relative w-full", className)}
      style={{ height }}
      role="img"
      aria-label={`${ariaLabel}. ${summary}.`}
    >
      {data.length === 0 && (
        <div className="flex h-full items-center justify-center text-sm text-muted">No data yet.</div>
      )}

      {data.length > 0 && width > 0 && layout && (
        <>
          <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" className={textClass[tone]} style={{ stopColor: "currentColor", stopOpacity: 0.28 }} />
                <stop offset="100%" className={textClass[tone]} style={{ stopColor: "currentColor", stopOpacity: 0 }} />
              </linearGradient>
            </defs>

            {layout.gridY.map((g, i) => (
              <line key={i} x1={PAD.left} x2={width - PAD.right} y1={g.y} y2={g.y} className="stroke-border" strokeWidth={1} />
            ))}

            {layout.areaPath && (
              <motion.path
                d={layout.areaPath}
                fill={`url(#${gradientId})`}
                stroke="none"
                initial={reduceMotion ? undefined : { opacity: 0 }}
                animate={reduceMotion ? undefined : { opacity: 1 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              />
            )}

            {layout.points.length === 1 ? (
              <circle cx={layout.points[0].x} cy={layout.points[0].y} r={4} className={fillClass[tone]} />
            ) : (
              <motion.path
                d={layout.linePath}
                fill="none"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                className={strokeClass[tone]}
                initial={reduceMotion ? undefined : { pathLength: 0 }}
                animate={reduceMotion ? undefined : { pathLength: 1 }}
                transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
              />
            )}

            {active && (
              <g className="pointer-events-none">
                <line x1={active.x} x2={active.x} y1={PAD.top} y2={PAD.top + innerH} className="stroke-border-strong" strokeWidth={1} strokeDasharray="3 3" />
                <circle cx={active.x} cy={active.y} r={4.5} className={fillClass[tone]} stroke="var(--bg-elevated)" strokeWidth={2} />
              </g>
            )}

            <rect
              x={PAD.left}
              y={0}
              width={innerW}
              height={height}
              fill="transparent"
              onMouseMove={onMove}
              onMouseLeave={() => setActiveIndex(null)}
            />
          </svg>

          {active && activeDatum && (
            <div
              className={cn(
                "pointer-events-none absolute top-1 -translate-y-0 rounded-md border border-border bg-bg-elevated px-2.5 py-1.5 text-xs shadow-md",
                tooltipAlignRight ? "-translate-x-full" : "",
              )}
              style={{ left: tooltipAlignRight ? tooltipLeft : tooltipLeft - 56 }}
            >
              <p className="font-medium text-text tabular-nums">{valueFormatter(activeDatum.value)}</p>
              <p className="text-subtle">{activeDatum.label}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
