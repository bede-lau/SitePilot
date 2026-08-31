import { UploadCloud } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useCallback, useRef, useState } from "react";
import type { DragEvent, ReactNode } from "react";
import { cn } from "../../lib/cn";

export interface DropzoneProps {
  onFiles: (files: File[]) => void;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}

/** Whole-panel drag overlay (PRD demo Minute 1:00) — wraps the chat panel so a PDF dropped
 * anywhere inside it shows a clear drop target instead of the browser's default "open file". Uses
 * a drag-enter depth counter so the overlay doesn't flicker as the pointer crosses child elements. */
export function Dropzone({ onFiles, children, className, disabled }: DropzoneProps) {
  const [active, setActive] = useState(false);
  const depthRef = useRef(0);
  const reduceMotion = useReducedMotion();

  const onDragEnter = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      if (disabled || !e.dataTransfer.types.includes("Files")) return;
      e.preventDefault();
      depthRef.current += 1;
      setActive(true);
    },
    [disabled],
  );

  const onDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    if (e.dataTransfer.types.includes("Files")) e.preventDefault();
  }, []);

  const onDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    depthRef.current = Math.max(0, depthRef.current - 1);
    if (depthRef.current === 0) setActive(false);
  }, []);

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      depthRef.current = 0;
      setActive(false);
      if (disabled) return;
      const files = Array.from(e.dataTransfer.files ?? []);
      if (files.length) onFiles(files);
    },
    [disabled, onFiles],
  );

  return (
    <div className={cn("relative", className)} onDragEnter={onDragEnter} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}>
      {children}
      <AnimatePresence>
        {active && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.15 }}
            className="pointer-events-none absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-accent bg-accent/10 backdrop-blur-[1px]"
          >
            <motion.div
              initial={reduceMotion ? undefined : { scale: 0.9 }}
              animate={reduceMotion ? undefined : { scale: 1 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="flex size-14 items-center justify-center rounded-full bg-accent text-accent-fg shadow-lg"
            >
              <UploadCloud className="size-6" aria-hidden="true" />
            </motion.div>
            <p className="text-sm font-medium text-text">Drop to upload</p>
            <p className="text-xs text-muted">Quotes, photos, or datasheets</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
