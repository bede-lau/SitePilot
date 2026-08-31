import { AlertTriangle, BadgeCheck, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { cn } from "../../lib/cn";
import { formatMYR, formatNumber } from "../../lib/format";
import { Badge, Card, CardBody, CardFooter, CardHeader, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, Tooltip } from "../ui";
import type { QuoteLineItem, SupplierQuote } from "../../lib/types";

function pricePerWp(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `RM ${v.toFixed(3)}/Wp`;
}

/** Line-item table with RM/Wp as the hero metric, animated BNEF Tier-1 badges, and flagged rows in
 * warning tone with the flag reason surfaced on hover. */
export function QuoteCard({ quote }: { quote: SupplierQuote }) {
  const [showAll, setShowAll] = useState(false);
  const rows = showAll ? quote.line_items : quote.line_items.slice(0, 5);

  return (
    <Card elevation="sm" className="overflow-hidden">
      <CardHeader>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text">{quote.supplier_name_raw}</p>
          <p className="truncate text-xs text-muted">{quote.source_filename}</p>
        </div>
        <Badge variant={quote.parse_status === "parsed" ? "success" : quote.parse_status === "partial" ? "warning" : "danger"}>{quote.parse_status}</Badge>
      </CardHeader>

      <div className="flex items-baseline gap-2 border-b border-border bg-bg-subtle/60 px-5 py-3">
        <span className="text-2xl font-semibold tabular-nums text-text">{pricePerWp(quote.summary.blended_price_per_wp_myr)}</span>
        <span className="text-xs text-muted">blended · {formatNumber(quote.summary.total_wp)} Wp total</span>
        {quote.summary.tier1_line_count > 0 && (
          <span className="ml-auto inline-flex items-center gap-1 text-xs text-success">
            <BadgeCheck className="size-3.5" aria-hidden="true" />
            {quote.summary.tier1_line_count} Tier 1
          </span>
        )}
      </div>

      <CardBody className="p-0">
        <Table>
          <TableHead>
            <tr>
              <TableHeaderCell>Item</TableHeaderCell>
              <TableHeaderCell>Qty</TableHeaderCell>
              <TableHeaderCell>Unit price</TableHeaderCell>
              <TableHeaderCell>RM/Wp</TableHeaderCell>
              <TableHeaderCell>Tier</TableHeaderCell>
            </tr>
          </TableHead>
          <TableBody>
            {rows.map((item) => (
              <LineItemRow key={item.line_no} item={item} />
            ))}
          </TableBody>
        </Table>
        {quote.line_items.length > 5 && (
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="flex w-full items-center justify-center gap-1 border-t border-border py-2 text-xs font-medium text-muted hover:text-text"
          >
            {showAll ? (
              <>
                Show fewer <ChevronUp className="size-3.5" aria-hidden="true" />
              </>
            ) : (
              <>
                Show all {quote.line_items.length} lines <ChevronDown className="size-3.5" aria-hidden="true" />
              </>
            )}
          </button>
        )}
      </CardBody>

      <CardFooter className="flex-col items-stretch gap-1">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted">Subtotal</span>
          <span className="font-medium tabular-nums text-text">{formatMYR(quote.subtotal_myr)}</span>
        </div>
        {quote.parse_notes && <p className="text-[11px] text-subtle">{quote.parse_notes}</p>}
      </CardFooter>
    </Card>
  );
}

function LineItemRow({ item }: { item: QuoteLineItem }) {
  const flagged = item.flags.length > 0;
  return (
    <TableRow className={cn(flagged && "bg-warning/[0.06]")}>
      <TableCell>
        <div className="flex items-start gap-1.5">
          {flagged && (
            <Tooltip content={item.flags.join(" · ")} side="top">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden="true" />
            </Tooltip>
          )}
          <div className="min-w-0">
            <p className="truncate font-medium text-text">
              {item.manufacturer ?? "—"} {item.model ?? ""}
            </p>
            <p className="truncate text-xs text-muted">{item.description}</p>
          </div>
        </div>
      </TableCell>
      <TableCell className="tabular-nums">
        {item.quantity} {item.unit}
      </TableCell>
      <TableCell className="tabular-nums">{formatMYR(item.unit_price_myr)}</TableCell>
      <TableCell className="tabular-nums">{pricePerWp(item.price_per_wp_myr)}</TableCell>
      <TableCell>
        {item.bnef_tier1 === true && <Badge variant="success">Tier 1</Badge>}
        {item.bnef_tier1 === false && <Badge variant="warning">Unlisted</Badge>}
        {item.bnef_tier1 === null && <span className="text-subtle">—</span>}
      </TableCell>
    </TableRow>
  );
}
