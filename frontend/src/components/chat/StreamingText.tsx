import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";

export interface StreamingTextProps {
  text: string;
  streaming: boolean;
  className?: string;
  /** Baseline reveal rate; the loop accelerates when it falls far behind the buffer. */
  charsPerSecond?: number;
}

/**
 * Reveals `text` at a capped characters/second rate so bursty SSE `delta` chunks still read as a
 * smooth stream rather than jumping in bursts. One long-lived rAF loop per streaming turn (reads
 * `text` through a ref) rather than restarting per delta. Snaps to full text immediately once
 * streaming ends, and is inert under `prefers-reduced-motion`.
 */
export function StreamingText({ text, streaming, className, charsPerSecond = 700 }: StreamingTextProps) {
  const reduceMotion = useReducedMotion();
  const textRef = useRef(text);
  const [revealed, setRevealed] = useState(() => (reduceMotion || !streaming ? text.length : 0));

  // Keep the ref in sync outside of render, without adding `text` to the rAF effect's deps below —
  // that would restart the loop on every bursty delta instead of smoothly catching up to it.
  useEffect(() => {
    textRef.current = text;
  }, [text]);

  useEffect(() => {
    if (reduceMotion || !streaming) {
      setRevealed(textRef.current.length);
      return;
    }

    let raf: number;
    let lastTs: number | null = null;
    function tick(ts: number) {
      if (lastTs === null) lastTs = ts;
      const dt = (ts - lastTs) / 1000;
      lastTs = ts;
      setRevealed((prev) => {
        const total = textRef.current.length;
        const behind = total - prev;
        // Baseline pace, but drain a large backlog within ~150ms so a burst of
        // deltas (or a slow first token then a flood) doesn't visibly crawl.
        const step = Math.max(1, dt * charsPerSecond, behind * dt * 7);
        return Math.min(total, prev + step);
      });
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [streaming, reduceMotion, charsPerSecond]);

  const shown = reduceMotion || !streaming ? text : text.slice(0, Math.floor(revealed));

  return (
    <span className={className}>
      {shown}
      {streaming && !reduceMotion && shown.length < text.length && (
        <span
          className="ml-0.5 inline-block h-[1em] w-0.5 -translate-y-px animate-pulse bg-accent align-middle"
          aria-hidden="true"
        />
      )}
    </span>
  );
}
