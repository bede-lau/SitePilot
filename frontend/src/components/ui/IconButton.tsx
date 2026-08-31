import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";
import type { ButtonVariant, ButtonSize } from "./Button";

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  icon: ReactNode;
  /** Required — an icon-only button must always have an accessible name. */
  "aria-label": string;
  variant?: Extract<ButtonVariant, "secondary" | "ghost" | "danger">;
  size?: ButtonSize;
}

const variantClasses: Record<string, string> = {
  secondary: "bg-surface text-text border border-border hover:bg-surface-hover",
  ghost: "bg-transparent text-muted hover:bg-surface-hover hover:text-text",
  danger: "bg-transparent text-danger hover:bg-surface-hover",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "size-8 rounded-md [&_svg]:size-3.5",
  md: "size-9 rounded-md [&_svg]:size-4",
  lg: "size-11 rounded-lg [&_svg]:size-5",
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon, variant = "ghost", size = "md", disabled, className, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled}
      className={cn(
        "inline-flex shrink-0 items-center justify-center transition-colors duration-[120ms] ease-out",
        "disabled:opacity-50 disabled:pointer-events-none",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {icon}
    </button>
  );
});
