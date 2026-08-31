import { useEffect, useState } from "react";
import { useReducedMotion } from "motion/react";

/* ─────────────────────────────────────────────────────────
 * LOADING STATE — pixel-grid loader for a pending assistant turn.
 *
 * Variants:
 *   Drive  — square cells, chevron wavefront driving right
 *   Dots   — same wavefront, circular cells
 *   Orbit  — a comet lapping the 3×3 perimeter
 *
 * Paired with a shimmering status label and a live elapsed
 * timer in mono tabular figures. Under prefers-reduced-motion
 * the grid freezes to its dim state; the timer still ticks.
 * ───────────────────────────────────────────────────────── */

const chevron = Array.from({ length: 9 }, (_, i) => {
  const r = Math.floor(i / 3);
  const c = i % 3;
  return (c + Math.abs(r - 1)) * 90;
});

const ORBIT_ORDER = [0, 1, 2, 5, 8, 7, 6, 3];
const orbit = Array.from({ length: 9 }, (_, i) => {
  const k = ORBIT_ORDER.indexOf(i);
  return k === -1 ? null : k * 110;
});

const PATTERNS: Record<string, { delays: (number | null)[]; dur: number; round: boolean }> = {
  Drive: { delays: chevron, dur: 650, round: false },
  Dots: { delays: chevron, dur: 650, round: true },
  Orbit: { delays: orbit, dur: 950, round: false },
};

function LoaderGrid({ delays, dur, round }: { delays: (number | null)[]; dur: number; round: boolean }) {
  return (
    <span aria-hidden className="grid shrink-0 grid-cols-[repeat(3,4px)] gap-[2px]">
      {delays.map((delay, index) => (
        <span
          key={index}
          className={`size-[4px] bg-accent ${round ? "rounded-full" : "rounded-[1px]"}`}
          style={{
            opacity: delay === null ? 0.14 : 0.28,
            animation: delay === null ? "none" : `fb-pixel-on ${dur}ms ease-in-out ${delay}ms infinite`,
          }}
        />
      ))}
    </span>
  );
}

function useElapsed() {
  const [ds, setDs] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setDs((d) => d + 1), 100);
    return () => clearInterval(t);
  }, []);
  const total = ds / 10;
  if (total < 60) return `${total.toFixed(1)}s`;
  return `${Math.floor(total / 60)}m ${(total % 60).toFixed(1)}s`;
}

export interface LoadingStateProps {
  /** Live status text from the SSE `status` event; falls back to "Thinking". */
  label?: string | null;
  variant?: "Drive" | "Dots" | "Orbit";
}

export function LoadingState({ label, variant = "Drive" }: LoadingStateProps) {
  const reduceMotion = useReducedMotion();
  const elapsed = useElapsed();
  const { delays, dur, round } = PATTERNS[variant] ?? PATTERNS.Drive;
  const resolved = (label ?? "").replace(/[.…]+$/, "").trim() || "Thinking";

  return (
    <div role="status" aria-live="polite" className="flex w-fit items-center gap-2.5">
      <LoaderGrid delays={delays} dur={dur} round={round} />
      <span
        className="bg-clip-text text-xs font-medium text-transparent"
        style={
          reduceMotion
            ? { color: "var(--text-muted)", WebkitTextFillColor: "var(--text-muted)" }
            : {
                backgroundImage:
                  "linear-gradient(90deg, var(--text-subtle) 35%, var(--text) 50%, var(--text-subtle) 65%)",
                backgroundSize: "200% 100%",
                animation: "fb-shimmer-text 1.4s linear infinite",
              }
        }
      >
        {resolved}
      </span>
      <span className="font-mono text-[11px] text-subtle tabular-nums">{elapsed}</span>
    </div>
  );
}
