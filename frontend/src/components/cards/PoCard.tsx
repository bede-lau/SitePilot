import { CheckCircle2, Send } from "lucide-react";
import { useState } from "react";
import { formatMYR } from "../../lib/format";
import { api } from "../../lib/api";
import { Badge, Button, Card, CardBody, CardFooter, CardHeader, useToast } from "../ui";
import type { DesignReport, PoGenerateResponse } from "../../lib/types";

export interface PoCardProps {
  /** Not-yet-generated design — renders the idle "Approve & Generate PO" button that calls the
   * API when clicked. Used by the `/feasibility` workbench (report.id is the feasibility_run_id). */
  report?: DesignReport;
  /** An already-completed PO — renders straight into the success state with no button. This is
   * what the chat `po_draft` card carries: `generate_po_package` (agents/tools.py) creates the PO,
   * PDF, and Telegram push as part of the tool call itself, so by the time the card reaches the UI
   * there is nothing left to approve — showing the idle button here would offer a second, duplicate
   * generation with no feasibility_run_id to call it with. */
  result?: PoGenerateResponse;
}

/** "Approve & Generate PO" → `POST /api/po/generate` → success state showing the PO number and
 * confirming the Telegram dispatch to the field engineer (PRD §6 closing beat). */
export function PoCard({ report, result: doneResult }: PoCardProps) {
  const { toast } = useToast();
  const [state, setState] = useState<"idle" | "generating" | "done" | "error">(doneResult ? "done" : "idle");
  const [result, setResult] = useState<{ poNumber: string; telegramSent: boolean } | null>(
    doneResult ? { poNumber: doneResult.po.po_number, telegramSent: doneResult.telegram_sent } : null,
  );

  async function approve() {
    if (!report) return;
    setState("generating");
    try {
      const res = await api.generatePO({ feasibility_run_id: report.id, notify_telegram: true });
      setResult({ poNumber: res.po.po_number, telegramSent: res.telegram_sent });
      setState("done");
      toast({ title: "Purchase order generated", description: res.po.po_number, variant: "success" });
    } catch {
      setState("error");
      toast({ title: "Couldn't generate the PO", description: "Try again in a moment.", variant: "danger" });
    }
  }

  const summaryLine = report
    ? `${report.array.module.manufacturer} ${report.array.module.model} × ${report.array.panel_count}`
    : doneResult?.po.item_description;
  const costValue = report ? report.financial.system_cost_myr : doneResult?.po.total_price_myr;

  return (
    <Card elevation="sm">
      <CardHeader>
        <p className="text-sm font-semibold text-text">Purchase order</p>
        {report && <Badge variant={report.status === "pass" ? "success" : "warning"}>{report.equipment_tier} tier</Badge>}
        {!report && doneResult && <Badge variant="success">{doneResult.po.status}</Badge>}
      </CardHeader>
      <CardBody className="space-y-2">
        {summaryLine && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted">{summaryLine}</span>
          </div>
        )}
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted">{report ? "Est. system cost" : "Total"}</span>
          <span className="font-medium tabular-nums text-text">{formatMYR(costValue)}</span>
        </div>
      </CardBody>
      <CardFooter>
        {state === "done" && result ? (
          <div className="flex w-full items-center gap-2 text-sm text-success">
            <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
            <span>
              <strong>{result.poNumber}</strong> generated{result.telegramSent ? " — sent to the field engineer's Telegram" : ""}
            </span>
          </div>
        ) : (
          <Button
            className="w-full"
            variant="primary"
            loading={state === "generating"}
            iconLeft={state !== "generating" ? <Send className="size-4" /> : undefined}
            onClick={approve}
            disabled={!report}
          >
            {state === "error" ? "Retry — Approve & Generate PO" : "Approve & Generate PO"}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
