import { cn } from "../../lib/cn";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: React.ReactNode;
}

export interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  "aria-label": string;
}

export function Segmented<T extends string>({ options, value, onChange, className, ...props }: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      className={cn("inline-flex items-center gap-0.5 rounded-md border border-border bg-bg-subtle p-0.5", className)}
      {...props}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-[calc(var(--radius-md)-2px)] px-3 py-1.5 text-xs font-medium",
              "transition-colors duration-[120ms] ease-out",
              selected ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text",
            )}
          >
            {option.icon}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
