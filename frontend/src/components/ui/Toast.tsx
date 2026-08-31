import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "../../lib/cn";
import { IconButton } from "./IconButton";

export type ToastVariant = "neutral" | "success" | "warning" | "danger" | "info";

export interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  /** ms before auto-dismiss. Set to 0 to require manual dismissal. */
  duration?: number;
}

interface ToastItem extends Required<Omit<ToastOptions, "description">> {
  id: string;
  description?: string;
}

interface ToastContextValue {
  toast: (options: ToastOptions) => string;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

const variantIcon: Record<ToastVariant, ReactNode> = {
  neutral: <Info className="size-4.5" aria-hidden="true" />,
  success: <CheckCircle2 className="size-4.5" aria-hidden="true" />,
  warning: <AlertTriangle className="size-4.5" aria-hidden="true" />,
  danger: <XCircle className="size-4.5" aria-hidden="true" />,
  info: <Info className="size-4.5" aria-hidden="true" />,
};

const variantClasses: Record<ToastVariant, string> = {
  neutral: "text-text",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const reduceMotion = useReducedMotion();

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const toast = useCallback(
    (options: ToastOptions) => {
      const id = crypto.randomUUID();
      const duration = options.duration ?? 5000;
      const item: ToastItem = {
        id,
        title: options.title,
        description: options.description,
        variant: options.variant ?? "neutral",
        duration,
      };
      setItems((prev) => [...prev, item]);
      if (duration > 0) {
        timers.current.set(
          id,
          setTimeout(() => dismiss(id), duration),
        );
      }
      return id;
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div
          className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-2"
          role="region"
          aria-label="Notifications"
        >
          <AnimatePresence>
            {items.map((item) => (
              <motion.div
                key={item.id}
                role="status"
                initial={{ opacity: 0, y: reduceMotion ? 0 : 12, scale: reduceMotion ? 1 : 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: reduceMotion ? 1 : 0.98 }}
                transition={{ duration: reduceMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
                className="pointer-events-auto flex items-start gap-3 rounded-lg border border-border bg-bg-elevated p-3.5 shadow-lg"
              >
                <span className={cn("mt-0.5 shrink-0", variantClasses[item.variant])}>{variantIcon[item.variant]}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text">{item.title}</p>
                  {item.description && <p className="mt-0.5 text-xs text-muted">{item.description}</p>}
                </div>
                <IconButton
                  icon={<X className="size-3.5" />}
                  aria-label="Dismiss notification"
                  size="sm"
                  onClick={() => dismiss(item.id)}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}
