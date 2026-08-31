import { motion, useReducedMotion } from "motion/react";
import { useMemo, useState } from "react";
import { cn } from "../../lib/cn";
import { bgClass, fillClass, type ChartTone } from "./tones";
import { scaleLinear, useElementSize } from "./utils";

export interface BarChartSeries {
  key: string;
  label: string;
  tone: ChartTone;
}

export interface BarChartDatum {
  label: string;
  values: Record<string, number>;
}

export interface BarChartProps {
  data: BarChartDatum[];
  series: BarChartSeries[];
  mode?: "grouped" | "stacked";
  height?: number;
  valueFormatter?: (value: number) => string;
  ariaLabel: string;
  className?: string;
}

const PAD = { top: 8, right: 4, bottom: 22, left: 4 };

export function BarChart({ data, series, mode = "grouped", height = 220, valueFormatter = String, ariaLabel, className }: BarChartProps) {
  const [containerRef, size] = useElementSize<HTMLDivElement>();
  const reduceMotion = useReducedMotion();
  const [hover, setHover] = useState<{ category: number; series: string } | null>(null);

  const width = size.width;
  const innerW = Math.max(0, width - PAD.left - PAD.right);
  const innerH = Math.max(0, height - PAD.top - PAD.bottom);

  const layout = useMemo(() => {
    if (data.length === 0 || width === 0) return null;

    const maxValue =
      mode === "stacked"
        ? Math.max(1, ...data.map((d) => series.reduce((sum, s) => sum + (d.values[s.key] ?? 0), 0)))
        : Math.max(1, ...data.flatMap((d) => series.map((s) => d.values[s.key] ?? 0)));

    const yScale = scaleLinear([0, maxValue], [PAD.top + innerH, PAD.top]);
    const bandWidth = innerW / data.length;
    const bandPad = bandWidth * 0.16;
    const usableBand = bandWidth - bandPad * 2;

    return { maxValue, yScale, bandWidth, bandPad, usableBand };
  }, [data, series, mode, width, innerW, innerH]);

  const summary = data.length === 0 ? "No data" : `${data.length} categories across ${series.length} series`;
  const baselineY = PAD.top + innerH;

  return (
    <div ref={containerRef} className={cn("w-full", className)} style={{ height }}>
      <div role="img" aria-label={`${ariaLabel}. ${summary}.`} className="h-full w-full">
        {series.length > 1 && (
          <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1">
            {series.map((s) => (
              <span key={s.key} className="inline-flex items-center gap-1.5 text-xs text-muted">
                <span className={cn("size-2 rounded-full", bgClass[s.tone])} aria-hidden="true" />
                {s.label}
              </span>
            ))}
          </div>
        )}

        {data.length === 0 && <div className="flex h-full items-center justify-center text-sm text-muted">No data yet.</div>}

        {data.length > 0 && width > 0 && layout && (
          <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
            <line x1={0} x2={width} y1={baselineY} y2={baselineY} className="stroke-border" strokeWidth={1} />

            {data.map((d, categoryIndex) => {
              const bandX = PAD.left + categoryIndex * layout.bandWidth + layout.bandPad;
              const showLabel = layout.bandWidth > 28 || categoryIndex % Math.ceil(24 / layout.bandWidth) === 0;

              if (mode === "stacked") {
                let cumulative = 0;
                return (
                  <g key={d.label}>
                    {series.map((s) => {
                      const value = d.values[s.key] ?? 0;
                      const yTop = layout.yScale(cumulative + value);
                      const yBottom = layout.yScale(cumulative);
                      cumulative += value;
                      const isHovered = hover?.category === categoryIndex && hover.series === s.key;
                      return (
                        <motion.rect
                          key={s.key}
                          x={bandX}
                          width={layout.usableBand}
                          y={reduceMotion ? yTop : baselineY}
                          height={reduceMotion ? Math.max(0, yBottom - yTop) : 0}
                          animate={{ y: yTop, height: Math.max(0, yBottom - yTop) }}
                          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: reduceMotion ? 0 : categoryIndex * 0.02 }}
                          rx={1.5}
                          className={fillClass[s.tone]}
                          opacity={isHovered ? 0.85 : 1}
                          onMouseEnter={() => setHover({ category: categoryIndex, series: s.key })}
                          onMouseLeave={() => setHover(null)}
                        >
                          <title>{`${d.label} · ${s.label}: ${valueFormatter(value)}`}</title>
                        </motion.rect>
                      );
                    })}
                    {showLabel && (
                      <text x={bandX + layout.usableBand / 2} y={baselineY + 14} textAnchor="middle" className="fill-subtle text-[10px]">
                        {d.label}
                      </text>
                    )}
                  </g>
                );
              }

              const subWidth = layout.usableBand / series.length;
              return (
                <g key={d.label}>
                  {series.map((s, seriesIndex) => {
                    const value = d.values[s.key] ?? 0;
                    const y = layout.yScale(value);
                    const isHovered = hover?.category === categoryIndex && hover.series === s.key;
                    return (
                      <motion.rect
                        key={s.key}
                        x={bandX + seriesIndex * subWidth + subWidth * 0.08}
                        width={subWidth * 0.84}
                        y={reduceMotion ? y : baselineY}
                        height={reduceMotion ? Math.max(0, baselineY - y) : 0}
                        animate={{ y, height: Math.max(0, baselineY - y) }}
                        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: reduceMotion ? 0 : categoryIndex * 0.03 + seriesIndex * 0.02 }}
                        rx={2}
                        className={fillClass[s.tone]}
                        opacity={isHovered ? 0.85 : 1}
                        onMouseEnter={() => setHover({ category: categoryIndex, series: s.key })}
                        onMouseLeave={() => setHover(null)}
                      >
                        <title>{`${d.label} · ${s.label}: ${valueFormatter(value)}`}</title>
                      </motion.rect>
                    );
                  })}
                  {showLabel && (
                    <text x={bandX + layout.usableBand / 2} y={baselineY + 14} textAnchor="middle" className="fill-subtle text-[10px]">
                      {d.label}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}
