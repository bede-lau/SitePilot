import { forwardRef } from "react";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export type CardElevation = "flat" | "sm" | "md" | "lg";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  elevation?: CardElevation;
  /** Adds a hover-lift affordance — use for clickable cards (project tiles, vendor tiles). */
  interactive?: boolean;
}

const elevationClasses: Record<CardElevation, string> = {
  flat: "shadow-none",
  sm: "shadow-sm",
  md: "shadow-md",
  lg: "shadow-lg",
};

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { elevation = "sm", interactive = false, className, ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border border-border bg-surface",
        elevationClasses[elevation],
        interactive &&
          "transition-all duration-[200ms] ease-out hover:border-border-strong hover:shadow-md hover:-translate-y-0.5",
        className,
      )}
      {...props}
    />
  );
});

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(function CardHeader(
  { className, ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn("flex items-center justify-between gap-3 border-b border-border px-5 py-4", className)}
      {...props}
    />
  );
});

export const CardBody = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(function CardBody(
  { className, ...props },
  ref,
) {
  return <div ref={ref} className={cn("px-5 py-4", className)} {...props} />;
});

export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(function CardFooter(
  { className, ...props },
  ref,
) {
  return (
    <div ref={ref} className={cn("flex items-center justify-between gap-3 border-t border-border px-5 py-3", className)} {...props} />
  );
});
