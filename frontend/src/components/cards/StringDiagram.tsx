import { motion, useReducedMotion } from "motion/react";
import { cn } from "../../lib/cn";

export interface StringDiagramProps {
  series: number;
  parallel: number;
  vmpString: number;
  vocString: number;
  moduleLabel: string;
  inverterLabel: string;
  className?: string;
}

const PANEL_W = 34;
const PANEL_H = 22;
const PANEL_GAP = 6;
const ROW_GAP = 16;
const LEFT_PAD = 16;
const COMBINER_GAP = 44;
const COMBINER_W = 96;

/**
 * Animated SVG of the series×parallel array wiring into the inverter — the single most
 * persuasive graphic in the demo (ARD §6.4). For 3S×5P this draws 5 parallel strings of 3 panels
 * each, wired to the inverter block, with the string Vmp/Voc labelled below. Strings draw in with
 * a stagger on mount; the inverter block settles in once the last string has landed.
 */
export function StringDiagram({ series, parallel, vmpString, vocString, moduleLabel, inverterLabel, className }: StringDiagramProps) {
  const reduceMotion = useReducedMotion();
  const rows = Math.max(1, parallel);
  const cols = Math.max(1, series);

  const rowHeight = PANEL_H + ROW_GAP;
  const stringWidth = cols * PANEL_W + (cols - 1) * PANEL_GAP;
  const height = rows * rowHeight + ROW_GAP / 2;
  const combinerX = LEFT_PAD + stringWidth + COMBINER_GAP;
  const width = combinerX + COMBINER_W + 8;

  return (
    <div className={cn("w-full", className)}>
      <div className="w-full overflow-x-auto rounded-lg border border-border bg-bg-subtle/40 p-3">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${cols} panels wired in series per string, ${rows} strings in parallel — ${cols * rows} panels total. String Vmp ${vmpString} volts, Voc ${vocString} volts, feeding the inverter.`}
          className="min-w-[420px]"
        >
          <motion.g
            initial={reduceMotion ? undefined : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, delay: reduceMotion ? 0 : rows * 0.1 + 0.15 }}
          >
            <rect x={combinerX} y={height / 2 - 34} width={COMBINER_W} height={68} rx={10} className="fill-bg-elevated stroke-border-strong" strokeWidth={1.5} />
            <text x={combinerX + COMBINER_W / 2} y={height / 2 - 6} textAnchor="middle" className="fill-text text-[10px] font-semibold">
              Inverter
            </text>
            <text x={combinerX + COMBINER_W / 2} y={height / 2 + 10} textAnchor="middle" className="fill-subtle text-[9px]">
              {inverterLabel}
            </text>
          </motion.g>

          {Array.from({ length: rows }, (_, r) => {
            const y = ROW_GAP / 2 + r * rowHeight;
            const midY = y + PANEL_H / 2;
            return (
              <motion.g
                key={r}
                initial={reduceMotion ? undefined : { opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.35, delay: reduceMotion ? 0 : r * 0.1, ease: [0.16, 1, 0.3, 1] }}
              >
                {Array.from({ length: cols }, (_, c) => {
                  const x = LEFT_PAD + c * (PANEL_W + PANEL_GAP);
                  return (
                    <g key={c}>
                      <rect x={x} y={y} width={PANEL_W} height={PANEL_H} rx={3} className="fill-accent/15 stroke-accent" strokeWidth={1.25} />
                      <line x1={x} y1={y + 4} x2={x + PANEL_W} y2={y + PANEL_H - 4} className="stroke-accent" strokeWidth={0.75} opacity={0.5} />
                      {c < cols - 1 && <line x1={x + PANEL_W} y1={midY} x2={x + PANEL_W + PANEL_GAP} y2={midY} className="stroke-border-strong" strokeWidth={1.5} />}
                    </g>
                  );
                })}
                <path
                  d={`M ${LEFT_PAD + stringWidth} ${midY} H ${combinerX - 12 - (rows - 1 - r) * 3} V ${height / 2} H ${combinerX}`}
                  fill="none"
                  className="stroke-border-strong"
                  strokeWidth={1.5}
                />
              </motion.g>
            );
          })}
        </svg>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
        <span>
          {cols}S × {rows}P = {cols * rows} panels
        </span>
        <span>
          String Vmp <strong className="text-text tabular-nums">{vmpString}V</strong>
        </span>
        <span>
          String Voc <strong className="text-text tabular-nums">{vocString}V</strong>
        </span>
        <span className="truncate">{moduleLabel}</span>
      </div>
    </div>
  );
}
