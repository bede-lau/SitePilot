import { Mic, Square, Trash2 } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useCallback, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { cn } from "../../lib/cn";
import { api } from "../../lib/api";
import { useVoiceRecorder } from "../../hooks/useVoiceRecorder";
import { useToast } from "../ui";

const CANCEL_DISTANCE_PX = 64;
const BUSY_STATUSES = new Set(["requesting", "recording", "processing"]);

export interface MicButtonProps {
  onTranscribed: (text: string) => void;
  disabled?: boolean;
  className?: string;
}

/** Press-and-hold voice note: hold to record with a live waveform, drag away to cancel, release to
 * transcribe via `POST /api/voice/transcribe` and hand the text back to the composer. */
export function MicButton({ onTranscribed, disabled, className }: MicButtonProps) {
  const { status, level, errorMessage, start, stopAndGetBlob, cancel } = useVoiceRecorder();
  const [dragCancel, setDragCancel] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const originRef = useRef<{ x: number; y: number } | null>(null);
  const reduceMotion = useReducedMotion();
  const { toast } = useToast();

  const recording = status === "recording";

  const onPointerDown = useCallback(
    async (e: ReactPointerEvent<HTMLButtonElement>) => {
      if (disabled || BUSY_STATUSES.has(status)) return;
      e.currentTarget.setPointerCapture(e.pointerId);
      originRef.current = { x: e.clientX, y: e.clientY };
      setDragCancel(false);
      await start();
    },
    [disabled, start, status],
  );

  const onPointerMove = useCallback((e: ReactPointerEvent<HTMLButtonElement>) => {
    if (!originRef.current) return;
    const dx = e.clientX - originRef.current.x;
    const dy = e.clientY - originRef.current.y;
    setDragCancel(Math.hypot(dx, dy) > CANCEL_DISTANCE_PX);
  }, []);

  const finish = useCallback(
    async (shouldCancel: boolean) => {
      originRef.current = null;
      if (status !== "recording") return;
      if (shouldCancel) {
        setDragCancel(false);
        await cancel();
        return;
      }
      setTranscribing(true);
      const blob = await stopAndGetBlob();
      setDragCancel(false);
      if (!blob) {
        setTranscribing(false);
        return;
      }
      try {
        const result = await api.transcribeVoice(blob);
        if (result.text.trim()) {
          onTranscribed(result.text.trim());
        } else {
          toast({ title: "No speech detected", description: "Try again a little closer to the mic.", variant: "warning" });
        }
      } catch {
        toast({ title: "Transcription failed", description: "Couldn't reach the voice service — try again.", variant: "danger" });
      } finally {
        setTranscribing(false);
      }
    },
    [cancel, onTranscribed, status, stopAndGetBlob, toast],
  );

  const onPointerUp = useCallback(
    (e: ReactPointerEvent<HTMLButtonElement>) => {
      e.currentTarget.releasePointerCapture(e.pointerId);
      finish(dragCancel);
    },
    [dragCancel, finish],
  );

  return (
    <div className={cn("relative", className)}>
      <button
        type="button"
        disabled={disabled || transcribing}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => finish(true)}
        aria-pressed={recording}
        aria-label={recording ? (dragCancel ? "Release to cancel recording" : "Recording — release to send") : "Hold to record a voice note"}
        className={cn(
          "relative inline-flex size-9 shrink-0 touch-none select-none items-center justify-center rounded-md transition-colors duration-[120ms]",
          recording ? (dragCancel ? "bg-danger text-danger-fg" : "bg-accent text-accent-fg") : "bg-transparent text-muted hover:bg-surface-hover hover:text-text",
          "disabled:opacity-50 disabled:pointer-events-none",
        )}
      >
        {recording && !reduceMotion && (
          <motion.span
            className="absolute inset-0 rounded-full bg-accent/40"
            animate={{ scale: 1 + level * 0.9, opacity: 0.5 - level * 0.2 }}
            transition={{ duration: 0.08 }}
          />
        )}
        {dragCancel ? (
          <Trash2 className="relative size-4" aria-hidden="true" />
        ) : recording ? (
          <Square className="relative size-3.5 fill-current" aria-hidden="true" />
        ) : (
          <Mic className="relative size-4" aria-hidden="true" />
        )}
      </button>

      <AnimatePresence>
        {recording && (
          <motion.div
            initial={reduceMotion ? undefined : { opacity: 0, y: 4, scale: 0.96 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 4, scale: 0.96 }}
            transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
            className={cn(
              "pointer-events-none absolute bottom-full right-0 z-10 mb-2 flex items-center gap-2 whitespace-nowrap rounded-lg border px-3 py-2 text-xs font-medium shadow-lg",
              dragCancel ? "border-danger/40 bg-danger/10 text-danger" : "border-border bg-bg-elevated text-text",
            )}
          >
            {dragCancel ? (
              "Release to cancel"
            ) : (
              <>
                <span className="flex items-center gap-0.5" aria-hidden="true">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <span key={i} className="w-0.5 rounded-full bg-accent" style={{ height: `${6 + level * 14 * Math.abs(Math.sin(i * 1.3 + level * 6))}px` }} />
                  ))}
                </span>
                Recording — drag away to cancel
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {errorMessage && (status === "denied" || status === "error") && (
        <p role="alert" className="absolute bottom-full right-0 z-10 mb-2 w-56 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger shadow-lg">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
