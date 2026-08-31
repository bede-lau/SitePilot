import { Loader2 } from "lucide-react";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner in place of `iconLeft` and disables the button. */
  loading?: boolean;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent-hover active:brightness-95",
  secondary: "bg-surface text-text border border-border hover:bg-surface-hover",
  ghost: "bg-transparent text-text hover:bg-surface-hover",
  danger: "bg-danger text-danger-fg hover:brightness-95",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs gap-1.5 rounded-md",
  md: "h-9 px-4 text-sm gap-2 rounded-md",
  lg: "h-11 px-5 text-base gap-2 rounded-lg",
};

const iconSizeClasses: Record<ButtonSize, string> = {
  sm: "size-3.5",
  md: "size-4",
  lg: "size-4.5",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, iconLeft, iconRight, disabled, className, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap font-medium",
        "transition-colors duration-[120ms] ease-out select-none",
        "disabled:opacity-50 disabled:pointer-events-none",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {loading ? (
        <Loader2 className={cn(iconSizeClasses[size], "animate-spin")} aria-hidden="true" />
      ) : (
        iconLeft
      )}
      {children}
      {!loading && iconRight}
    </button>
  );
});
