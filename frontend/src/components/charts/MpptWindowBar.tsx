import { motion, useReducedMotion } from "motion/react";
import { cn } from "../../lib/cn";
import { scaleLinear, useElementSize } from "./utils";

export interface MpptWindowBarProps {
  mpptMinV: number;
  mpptMaxV: number;
  maxDcVoltageV: number;
  vmpString: number;
  vocString: number;
  /** Cold-temperature Voc — the worst-case value that actually matters against the hard limit. */
  vocColdString?: number;
  height?: number;
  ariaLabel: string;
  className?: string;
}

const PAD_X = 8;

/**
 * The single most persuasive graphic in the demo (ARD §6.4): the inverter's MPPT operating
 * window as a band, the absolute max DC voltage as a hard limit, and the string's Vmp/Voc plotted
 * inside it. When everything sits inside the window this should read instantly as "it fits".
 */
export function MpptWindowBar({ mpptMinV, mpptMaxV, maxDcVoltageV, vmpString, vocString, vocColdString, height = 128, ariaLabel, className }: MpptWindowBarProps) {
  const [containerRef, size] = useElementSize<HTMLDivElement>();
  const reduceMotion = useReducedMotion();
  const width = size.width;

  const worstVoc = vocColdString ?? vocString;
  const domainMax = Math.max(maxDcVoltageV, worstVoc, mpptMaxV) * 1.08;
  const trackY = height - 34;
  const innerWidth = Math.max(0, width - PAD_X * 2);

  const xScale = scaleLinear([0, domainMax], [PAD_X, PAD_X + innerWidth]);

  const vmpPass = vmpString >= mpptMinV && vmpString <= mpptMaxV;
  const vocPass = worstVoc < maxDcVoltageV;

  const vmpX = xScale(vmpString);
  const vocX = xScale(worstVoc);
  const labelsClose = Math.abs(vmpX - vocX) < 88;

  const summary = `MPPT window ${mpptMinV} to ${mpptMaxV} volts. String Vmp ${vmpString} volts, ${vmpPass ? "inside the window" : "outside the window"}. Cold Voc ${worstVoc} volts against a ${maxDcVoltageV} volt hard limit, ${vocPass ? "within limit" : "exceeds limit"}.`;

  return (
    <div ref={containerRef} className={cn("w-full", className)} style={{ height }} role="img" aria-label={`${ariaLabel}. ${summary}`}>
      {width > 0 && (
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
          {/* base track */}
          <line x1={PAD_X} x2={PAD_X + innerWidth} y1={trackY} y2={trackY} className="stroke-border-strong" strokeWidth={2} strokeLinecap="round" />

          {/* MPPT operating window band */}
          <motion.rect
            x={xScale(mpptMinV)}
            y={trackY - 10}
            width={Math.max(0, xScale(mpptMaxV) - xScale(mpptMinV))}
            height={20}
            rx={6}
            className="fill-success stroke-success"
            strokeWidth={1}
            fillOpacity={0.16}
            strokeOpacity={0.5}
            initial={reduceMotion ? undefined : { opacity: 0, scaleX: 0.9 }}
            animate={reduceMotion ? undefined : { opacity: 1, scaleX: 1 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            style={{ transformOrigin: `${xScale((mpptMinV + mpptMaxV) / 2)}px ${trackY}px` }}
          />
          <text x={xScale((mpptMinV + mpptMaxV) / 2)} y={trackY - 18} textAnchor="middle" className="fill-success text-[10px] font-medium">
            MPPT window {mpptMinV}–{mpptMaxV}V
          </text>

          {/* absolute max DC voltage — hard limit */}
          <line x1={xScale(maxDcVoltageV)} x2={xScale(maxDcVoltageV)} y1={8} y2={trackY + 16} className="stroke-danger" strokeWidth={1.5} strokeDasharray="4 3" />
          <text
            x={xScale(maxDcVoltageV)}
            y={10}
            textAnchor={xScale(maxDcVoltageV) > width - 90 ? "end" : "start"}
            dx={xScale(maxDcVoltageV) > width - 90 ? -4 : 4}
            dy={8}
            className="fill-danger text-[10px] font-medium"
          >
            Max DC {maxDcVoltageV}V
          </text>

          {/* Voc (cold) marker */}
          <motion.g
            initial={reduceMotion ? undefined : { opacity: 0, y: -6 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
          >
            <line x1={vocX} x2={vocX} y1={trackY - 24} y2={trackY + 10} className={vocPass ? "stroke-accent" : "stroke-danger"} strokeWidth={2} />
            <circle cx={vocX} cy={trackY - 24} r={4} className={vocPass ? "fill-accent" : "fill-danger"} />
            <text
              x={vocX}
              y={labelsClose ? trackY - 44 : trackY - 30}
              textAnchor="middle"
              className={cn("text-[10px] font-medium tabular-nums", vocPass ? "fill-accent" : "fill-danger")}
            >
              Voc(cold) {worstVoc}V
            </text>
          </motion.g>

          {/* Vmp marker */}
          <motion.g
            initial={reduceMotion ? undefined : { opacity: 0, y: -6 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
          >
            <line x1={vmpX} x2={vmpX} y1={trackY - 16} y2={trackY + 10} className={vmpPass ? "stroke-success" : "stroke-danger"} strokeWidth={2} />
            <circle cx={vmpX} cy={trackY - 16} r={4} className={vmpPass ? "fill-success" : "fill-danger"} />
            <text
              x={vmpX}
              y={labelsClose ? trackY + 30 : trackY - 22}
              textAnchor="middle"
              className={cn("text-[10px] font-medium tabular-nums", vmpPass ? "fill-success" : "fill-danger")}
            >
              Vmp {vmpString}V
            </text>
          </motion.g>

          {/* axis endpoints */}
          <text x={PAD_X} y={trackY + 26} textAnchor="start" className="fill-subtle text-[10px]">0V</text>
          <text x={PAD_X + innerWidth} y={trackY + 26} textAnchor="end" className="fill-subtle text-[10px]">{Math.round(domainMax)}V</text>
        </svg>
      )}
    </div>
  );
}
