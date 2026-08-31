import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react";
import type { ReactNode, TableHTMLAttributes, ThHTMLAttributes, TdHTMLAttributes, HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export type SortDirection = "asc" | "desc" | null;

export interface TableProps extends TableHTMLAttributes<HTMLTableElement> {
  /** Wraps the table in its own horizontal scroll container — the page itself never scrolls sideways. */
  containerClassName?: string;
}

export function Table({ className, containerClassName, ...props }: TableProps) {
  return (
    <div className={cn("w-full overflow-x-auto rounded-lg border border-border", containerClassName)}>
      <table className={cn("w-full min-w-max text-left text-sm", className)} {...props} />
    </div>
  );
}

export function TableHead({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn("sticky top-0 z-10 bg-bg-subtle text-xs font-medium text-muted", className)}
      {...props}
    />
  );
}

export function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("divide-y divide-border", className)} {...props} />;
}

export function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("transition-colors duration-[120ms] hover:bg-surface-hover", className)} {...props} />;
}

export interface TableHeaderCellProps extends ThHTMLAttributes<HTMLTableCellElement> {
  sortKey?: string;
  currentSort?: { key: string; direction: SortDirection };
  onSort?: (key: string) => void;
}

export function TableHeaderCell({
  sortKey,
  currentSort,
  onSort,
  className,
  children,
  ...props
}: TableHeaderCellProps) {
  const sortable = Boolean(sortKey && onSort);
  const active = sortable && currentSort?.key === sortKey;
  const direction = active ? currentSort?.direction : null;

  if (!sortable) {
    return (
      <th scope="col" className={cn("whitespace-nowrap px-4 py-3 font-medium", className)} {...props}>
        {children}
      </th>
    );
  }

  return (
    <th scope="col" className={cn("whitespace-nowrap px-4 py-3 font-medium", className)} {...props}>
      <button
        type="button"
        onClick={() => onSort?.(sortKey!)}
        aria-sort={active ? (direction === "asc" ? "ascending" : direction === "desc" ? "descending" : "none") : "none"}
        className="inline-flex items-center gap-1 text-inherit hover:text-text"
      >
        {children}
        {active && direction === "asc" && <ChevronUp className="size-3.5" aria-hidden="true" />}
        {active && direction === "desc" && <ChevronDown className="size-3.5" aria-hidden="true" />}
        {!active && <ChevronsUpDown className="size-3.5 text-subtle" aria-hidden="true" />}
      </button>
    </th>
  );
}

export function TableCell({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("whitespace-nowrap px-4 py-3 text-text", className)} {...props} />;
}

export function TableEmptyRow({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-10 text-center text-sm text-muted">
        {children}
      </td>
    </tr>
  );
}
