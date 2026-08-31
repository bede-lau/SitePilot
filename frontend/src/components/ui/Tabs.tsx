import { createContext, useContext, useId, useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import { cn } from "../../lib/cn";

interface TabsContextValue {
  value: string;
  setValue: (value: string) => void;
  idBase: string;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(component: string): TabsContextValue {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error(`<${component}> must be used inside <Tabs>`);
  return ctx;
}

export interface TabsProps {
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
  className?: string;
}

export function Tabs({ value, onChange, children, className }: TabsProps) {
  const idBase = useId();
  return (
    <TabsContext.Provider value={{ value, setValue: onChange, idBase }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export interface TabListProps {
  children: ReactNode;
  className?: string;
  "aria-label": string;
}

export function TabList({ children, className, ...props }: TabListProps) {
  const listRef = useRef<HTMLDivElement>(null);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
    const tabs = Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? []);
    const currentIndex = tabs.findIndex((t) => t === document.activeElement);
    if (currentIndex === -1) return;
    e.preventDefault();
    let nextIndex = currentIndex;
    if (e.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (e.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    if (e.key === "Home") nextIndex = 0;
    if (e.key === "End") nextIndex = tabs.length - 1;
    tabs[nextIndex]?.focus();
    tabs[nextIndex]?.click();
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      onKeyDown={onKeyDown}
      className={cn("flex items-center gap-1 border-b border-border", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export interface TabProps {
  value: string;
  children: ReactNode;
  className?: string;
}

export function Tab({ value, children, className }: TabProps) {
  const { value: active, setValue, idBase } = useTabsContext("Tab");
  const selected = active === value;

  return (
    <button
      type="button"
      role="tab"
      id={`${idBase}-tab-${value}`}
      aria-selected={selected}
      aria-controls={`${idBase}-panel-${value}`}
      tabIndex={selected ? 0 : -1}
      onClick={() => setValue(value)}
      className={cn(
        "relative -mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors duration-[120ms] ease-out",
        selected ? "border-accent text-text" : "border-transparent text-muted hover:text-text",
        className,
      )}
    >
      {children}
    </button>
  );
}

export interface TabPanelProps {
  value: string;
  children: ReactNode;
  className?: string;
}

export function TabPanel({ value, children, className }: TabPanelProps) {
  const { value: active, idBase } = useTabsContext("TabPanel");
  if (active !== value) return null;

  return (
    <div
      role="tabpanel"
      id={`${idBase}-panel-${value}`}
      aria-labelledby={`${idBase}-tab-${value}`}
      tabIndex={0}
      className={cn("animate-fade-in", className)}
    >
      {children}
    </div>
  );
}
