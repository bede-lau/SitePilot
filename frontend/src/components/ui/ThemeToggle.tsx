import { Laptop, Moon, Sun } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";
import { cn } from "../../lib/cn";
import { applyTheme, getStoredPreference, setThemePreference, type ThemePreference } from "../../lib/theme";

const OPTIONS: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light theme", icon: Sun },
  { value: "system", label: "Match system theme", icon: Laptop },
  { value: "dark", label: "Dark theme", icon: Moon },
];

export interface ThemeToggleProps {
  className?: string;
}

/**
 * Three-state light/dark/system switch. The actual theme is applied to `documentElement` before
 * first paint by the inline bootstrap script in index.html — this component only needs to reflect
 * and change the stored preference from then on.
 */
export function ThemeToggle({ className }: ThemeToggleProps) {
  const [pref, setPref] = useState<ThemePreference>(() => getStoredPreference());
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    applyTheme(pref);
  }, [pref]);

  function select(next: ThemePreference) {
    setPref(next);
    setThemePreference(next);
  }

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className={cn("relative inline-flex items-center gap-0.5 rounded-md border border-border bg-bg-subtle p-0.5", className)}
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = pref === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            onClick={() => select(value)}
            className="relative inline-flex size-7 items-center justify-center rounded-[calc(var(--radius-md)-2px)] text-muted transition-colors duration-[120ms] ease-out hover:text-text"
          >
            {active && (
              <motion.span
                layoutId="theme-toggle-active"
                className="absolute inset-0 rounded-[calc(var(--radius-md)-2px)] bg-surface shadow-sm"
                transition={{ duration: reduceMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
              />
            )}
            <Icon className={cn("relative size-4", active && "text-text")} aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
