import { useId, useState } from "react";
import type { ReactElement, ReactNode } from "react";
import { cloneElement, isValidElement } from "react";
import { cn } from "../../lib/cn";

export type TooltipSide = "top" | "bottom" | "left" | "right";

export interface TooltipProps {
  content: ReactNode;
  side?: TooltipSide;
  children: ReactElement;
  className?: string;
}

const sideClasses: Record<TooltipSide, string> = {
  top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
  left: "right-full top-1/2 -translate-y-1/2 mr-2",
  right: "left-full top-1/2 -translate-y-1/2 ml-2",
};

/**
 * Shows on hover AND focus (keyboard users get the same information as mouse users) via a plain
 * CSS opacity/scale transition — no JS animation library needed, and it inherits the app-wide
 * `prefers-reduced-motion` transition kill in index.css automatically.
 */
export function Tooltip({ content, side = "top", children, className }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const id = useId();

  if (!isValidElement(children)) return children;

  const trigger = cloneElement(children as ReactElement<Record<string, unknown>>, {
    "aria-describedby": id,
    onMouseEnter: (e: React.MouseEvent) => {
      setOpen(true);
      (children.props as { onMouseEnter?: (e: React.MouseEvent) => void }).onMouseEnter?.(e);
    },
    onMouseLeave: (e: React.MouseEvent) => {
      setOpen(false);
      (children.props as { onMouseLeave?: (e: React.MouseEvent) => void }).onMouseLeave?.(e);
    },
    onFocus: (e: React.FocusEvent) => {
      setOpen(true);
      (children.props as { onFocus?: (e: React.FocusEvent) => void }).onFocus?.(e);
    },
    onBlur: (e: React.FocusEvent) => {
      setOpen(false);
      (children.props as { onBlur?: (e: React.FocusEvent) => void }).onBlur?.(e);
    },
  });

  return (
    <span className="relative inline-flex">
      {trigger}
      <span
        role="tooltip"
        id={id}
        className={cn(
          "pointer-events-none absolute z-50 whitespace-nowrap rounded-md border border-border bg-bg-elevated px-2.5 py-1.5 text-xs font-medium text-text shadow-md",
          "transition-[opacity,transform] duration-[120ms] ease-out",
          open ? "opacity-100 scale-100" : "opacity-0 scale-95",
          sideClasses[side],
          className,
        )}
      >
        {content}
      </span>
    </span>
  );
}
