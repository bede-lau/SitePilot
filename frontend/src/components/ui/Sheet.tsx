import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { X } from "lucide-react";
import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "../../lib/cn";
import { IconButton } from "./IconButton";

export type SheetSide = "left" | "right" | "bottom";

export interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  side?: SheetSide;
  title?: string;
  children?: ReactNode;
  className?: string;
}

const panelPositionClasses: Record<SheetSide, string> = {
  left: "inset-y-0 left-0 h-full w-full max-w-sm border-r",
  right: "inset-y-0 right-0 h-full w-full max-w-sm border-l",
  bottom: "inset-x-0 bottom-0 max-h-[85vh] w-full rounded-t-xl border-t",
};

function offscreenTransform(side: SheetSide) {
  if (side === "left") return { x: "-100%" };
  if (side === "right") return { x: "100%" };
  return { y: "100%" };
}

export function Sheet({ open, onOpenChange, side = "right", title, children, className }: SheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onOpenChange(false);
    }

    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onOpenChange]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div
            className="absolute inset-0 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.2 }}
            onClick={() => onOpenChange(false)}
            aria-hidden="true"
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={title ? titleId : undefined}
            tabIndex={-1}
            initial={reduceMotion ? { opacity: 0 } : offscreenTransform(side)}
            animate={reduceMotion ? { opacity: 1 } : { x: 0, y: 0 }}
            exit={reduceMotion ? { opacity: 0 } : offscreenTransform(side)}
            transition={{ duration: reduceMotion ? 0 : 0.32, ease: [0.16, 1, 0.3, 1] }}
            className={cn(
              "absolute flex flex-col border-border bg-bg-elevated shadow-lg outline-none",
              panelPositionClasses[side],
              className,
            )}
          >
            {title && (
              <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
                <h2 id={titleId} className="text-md font-semibold text-text">
                  {title}
                </h2>
                <IconButton icon={<X />} aria-label="Close" onClick={() => onOpenChange(false)} />
              </div>
            )}
            <div className="flex-1 overflow-y-auto">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
