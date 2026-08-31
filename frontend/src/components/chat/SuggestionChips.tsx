import { FileSearch2, Sparkles, Zap } from "lucide-react";
import { cn } from "../../lib/cn";

export interface SuggestionChipsProps {
  onSelect: (prompt: string) => void;
  className?: string;
  disabled?: boolean;
}

/** Seeded with the PRD §6 demo prompts (Minute 1:00 quote parse, Minute 2:15 feasibility check),
 * plus one financial follow-up so the empty state hints at the full demo arc. */
const SUGGESTIONS = [
  { icon: FileSearch2, text: "Extract this quote, normalize the unit economics, and check manufacturer tier status." },
  { icon: Zap, text: "Can we pair these panels with a standard 10kW Huawei string inverter?" },
  { icon: Sparkles, text: "What's the payback period for the Greenfield project?" },
];

export function SuggestionChips({ onSelect, className, disabled }: SuggestionChipsProps) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {SUGGESTIONS.map((s) => (
        <button
          key={s.text}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(s.text)}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-left text-xs text-muted transition-colors duration-[120ms] hover:border-border-strong hover:text-text disabled:opacity-50 disabled:pointer-events-none"
        >
          <s.icon className="size-3.5 shrink-0 text-accent" aria-hidden="true" />
          <span className="line-clamp-1">{s.text}</span>
        </button>
      ))}
    </div>
  );
}
