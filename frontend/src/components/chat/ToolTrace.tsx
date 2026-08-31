import { Check, ChevronDown, Loader2, Wrench, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import { cn } from "../../lib/cn";
import type { ToolTraceEntry } from "../../hooks/useChatSession";

const TOOL_LABELS: Record<string, string> = {
  parse_supplier_quote: "Parsing supplier quote",
  run_feasibility: "Running feasibility check",
  generate_bos_spec: "Generating BOS spec",
  financial_analysis: "Running financial analysis",
  list_components: "Searching component catalog",
  check_bnef_tier: "Checking BNEF tier",
  generate_po_package: "Generating purchase order",
  list_projects: "Looking up projects",
  get_project: "Loading project",
  list_inspections: "Loading inspections",
  list_invoices: "Loading invoices",
  list_purchase_orders: "Loading purchase orders",
  find_vendors: "Finding vendors",
  start_procurement: "Starting procurement",
  draft_invoice: "Drafting invoice",
};

function labelFor(name: string): string {
  return TOOL_LABELS[name] ?? name.replace(/_/g, " ");
}

/** Collapsible chip strip driven by `tool` / `tool_result` SSE events — makes the agent's tool
 * calls legible: name, spinner while running, then a check/cross plus elapsed ms. */
export function ToolTrace({ entries }: { entries: ToolTraceEntry[] }) {
  const [open, setOpen] = useState(true);
  const reduceMotion = useReducedMotion();
  if (entries.length === 0) return null;

  const runningCount = entries.filter((e) => e.status === "running").length;

  return (
    <div className="rounded-lg border border-border bg-bg-subtle/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-muted transition-colors hover:text-text"
        aria-expanded={open}
      >
        <Wrench className="size-3.5 shrink-0" aria-hidden="true" />
        <span className="flex-1">
          {runningCount > 0 ? `Working — ${runningCount} tool${runningCount > 1 ? "s" : ""} running` : `${entries.length} tool${entries.length > 1 ? "s" : ""} used`}
        </span>
        <ChevronDown className={cn("size-3.5 shrink-0 transition-transform duration-[200ms]", open && "rotate-180")} aria-hidden="true" />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={reduceMotion ? undefined : { height: 0, opacity: 0 }}
            animate={reduceMotion ? undefined : { height: "auto", opacity: 1 }}
            exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <ul className="flex flex-col gap-1 px-3 pb-2.5">
              {entries.map((entry) => (
                <li key={entry.key} className="flex items-center gap-2 text-xs">
                  {entry.status === "running" && <Loader2 className="size-3.5 shrink-0 animate-spin text-accent" aria-hidden="true" />}
                  {entry.status === "ok" && <Check className="size-3.5 shrink-0 text-success" aria-hidden="true" />}
                  {entry.status === "error" && <X className="size-3.5 shrink-0 text-danger" aria-hidden="true" />}
                  <span className={cn("flex-1 truncate", entry.status === "error" ? "text-danger" : "text-text")}>{labelFor(entry.name)}</span>
                  {entry.ms !== undefined && <span className="shrink-0 tabular-nums text-subtle">{entry.ms}ms</span>}
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
