import { Search } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "../../lib/cn";

export interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon?: ReactNode;
  shortcut?: string;
  keywords?: string[];
  onSelect: () => void;
}

export interface CommandGroup {
  heading: string;
  items: CommandItem[];
}

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groups: CommandGroup[];
  placeholder?: string;
}

/** Registers the ⌘K / Ctrl+K global shortcut. Call once, e.g. from the shell Layout. */
export function useCommandPaletteHotkey(onToggle: () => void) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onToggle();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onToggle]);
}

/** Subsequence fuzzy match: every query char must appear in order in the target. Lower is better. */
function fuzzyScore(query: string, target: string): number | null {
  if (!query) return 0;
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  const idx = t.indexOf(q);
  if (idx !== -1) return idx; // substring match ranks by position — earlier is better

  let qi = 0;
  let score = 0;
  let lastMatch = -1;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      score += lastMatch === -1 ? 0 : ti - lastMatch - 1; // penalize gaps between matched chars
      lastMatch = ti;
      qi++;
    }
  }
  return qi === q.length ? 1000 + score : null; // subsequence matches rank behind substring ones
}

export function CommandPalette({ open, onOpenChange, groups, placeholder = "Type a command or search…" }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const reduceMotion = useReducedMotion();

  const filteredGroups = useMemo(() => {
    if (!query.trim()) return groups;
    return groups
      .map((group) => {
        const scored = group.items
          .map((item) => {
            const haystack = [item.label, item.description, ...(item.keywords ?? [])].filter(Boolean).join(" ");
            const score = fuzzyScore(query, haystack);
            return score === null ? null : { item, score };
          })
          .filter((x): x is { item: CommandItem; score: number } => x !== null)
          .sort((a, b) => a.score - b.score)
          .map((x) => x.item);
        return { heading: group.heading, items: scored };
      })
      .filter((group) => group.items.length > 0);
  }, [groups, query]);

  const flatItems = useMemo(() => filteredGroups.flatMap((g) => g.items), [filteredGroups]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      onOpenChange(false);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, flatItems.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = flatItems[activeIndex];
      if (item) {
        item.onSelect();
        onOpenChange(false);
      }
    }
  }

  let runningIndex = -1;

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[70] flex items-start justify-center px-4 pt-[15vh]">
          <motion.div
            className="absolute inset-0 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.15 }}
            onClick={() => onOpenChange(false)}
            aria-hidden="true"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            initial={{ opacity: 0, scale: reduceMotion ? 1 : 0.97, y: reduceMotion ? 0 : -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: reduceMotion ? 1 : 0.97, y: reduceMotion ? 0 : -8 }}
            transition={{ duration: reduceMotion ? 0 : 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="relative flex max-h-[60vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-border bg-bg-elevated shadow-lg"
          >
            <div className="flex items-center gap-2.5 border-b border-border px-4 py-3">
              <Search className="size-4 shrink-0 text-subtle" aria-hidden="true" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={placeholder}
                aria-label="Search commands"
                role="combobox"
                aria-expanded={open}
                aria-controls="command-palette-list"
                aria-activedescendant={flatItems[activeIndex] ? `command-item-${flatItems[activeIndex].id}` : undefined}
                className="w-full bg-transparent text-sm text-text placeholder:text-subtle focus:outline-none"
              />
              <kbd className="shrink-0 rounded border border-border px-1.5 py-0.5 text-[10px] font-medium text-subtle">Esc</kbd>
            </div>

            <div id="command-palette-list" role="listbox" className="flex-1 overflow-y-auto p-2">
              {flatItems.length === 0 && (
                <p className="px-3 py-6 text-center text-sm text-muted">No matching commands.</p>
              )}
              {filteredGroups.map((group) => (
                <div key={group.heading} className="mb-1 last:mb-0">
                  <p className="px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-subtle">{group.heading}</p>
                  {group.items.map((item) => {
                    runningIndex++;
                    const isActive = runningIndex === activeIndex;
                    return (
                      <button
                        key={item.id}
                        id={`command-item-${item.id}`}
                        role="option"
                        aria-selected={isActive}
                        type="button"
                        onMouseEnter={() => setActiveIndex(runningIndex)}
                        onClick={() => {
                          item.onSelect();
                          onOpenChange(false);
                        }}
                        className={cn(
                          "flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm transition-colors duration-[120ms]",
                          isActive ? "bg-accent text-accent-fg" : "text-text hover:bg-surface-hover",
                        )}
                      >
                        {item.icon && <span className="shrink-0 [&_svg]:size-4">{item.icon}</span>}
                        <span className="flex-1 min-w-0">
                          <span className="block truncate">{item.label}</span>
                          {item.description && (
                            <span className={cn("block truncate text-xs", isActive ? "text-accent-fg/80" : "text-muted")}>
                              {item.description}
                            </span>
                          )}
                        </span>
                        {item.shortcut && (
                          <kbd
                            className={cn(
                              "shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium",
                              isActive ? "border-accent-fg/30 text-accent-fg" : "border-border text-subtle",
                            )}
                          >
                            {item.shortcut}
                          </kbd>
                        )}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
