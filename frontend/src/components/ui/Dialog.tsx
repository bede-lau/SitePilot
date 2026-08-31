import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { X } from "lucide-react";
import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "../../lib/cn";
import { IconButton } from "./IconButton";

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeClasses = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-2xl" };

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function Dialog({ open, onOpenChange, title, description, children, footer, size = "md", className }: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descId = useId();
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!open) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    panel?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onOpenChange(false);
        return;
      }
      if (e.key !== "Tab" || !panel) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => !el.hasAttribute("disabled"));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
      previouslyFocused?.focus?.();
    };
  }, [open, onOpenChange]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
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
            aria-labelledby={titleId}
            aria-describedby={description ? descId : undefined}
            tabIndex={-1}
            initial={{ opacity: 0, scale: reduceMotion ? 1 : 0.96, y: reduceMotion ? 0 : 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: reduceMotion ? 1 : 0.96, y: reduceMotion ? 0 : 8 }}
            transition={{ duration: reduceMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={cn(
              "relative w-full rounded-xl border border-border bg-bg-elevated shadow-lg outline-none",
              sizeClasses[size],
              className,
            )}
          >
            <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
              <div>
                <h2 id={titleId} className="text-md font-semibold text-text">
                  {title}
                </h2>
                {description && (
                  <p id={descId} className="mt-0.5 text-sm text-muted">
                    {description}
                  </p>
                )}
              </div>
              <IconButton icon={<X />} aria-label="Close dialog" onClick={() => onOpenChange(false)} />
            </div>
            {children && <div className="px-5 py-4">{children}</div>}
            {footer && <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">{footer}</div>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
