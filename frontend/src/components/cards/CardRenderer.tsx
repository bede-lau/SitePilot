import type { BosSpec, ChatCard, ConfidenceScore, DesignReport, FinancialModel, PoGenerateResponse, Project, ProjectDetail, SupplierQuote, Vendor } from "../../lib/types";
import { BosSpecCard } from "./BosSpecCard";
import { ComponentPickCard } from "./ComponentPickCard";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { FeasibilityCard } from "./FeasibilityCard";
import { FinancialCard } from "./FinancialCard";
import { PoCard } from "./PoCard";
import { ProjectSummaryCard } from "./ProjectSummaryCard";
import { QuoteCard } from "./QuoteCard";
import { RfqStatusCard } from "./RfqStatusCard";
import { VendorListCard } from "./VendorListCard";

/** Maps a `card` SSE event (or a persisted `ChatCard`) to its component — one per `card_type` in
 * ARD §5.5. Rendering never recomputes a number: each card renders exactly the payload it's given. */
export function CardRenderer({ card }: { card: ChatCard }) {
  switch (card.card_type) {
    case "quote_parsed":
      return <QuoteCard quote={card.data as SupplierQuote} />;
    case "feasibility":
      return <FeasibilityCard report={card.data as DesignReport} />;
    case "bos_spec":
      return <BosSpecCard bos={card.data as BosSpec} />;
    case "financial":
      return <FinancialCard financial={card.data as FinancialModel} />;
    case "confidence":
      return <ConfidenceBadge confidence={card.data as ConfidenceScore} />;
    case "po_draft":
      // agents/tools.py's generate_po_package already creates the PO (DB row, PDF, Telegram push)
      // as part of the tool call, so this card's payload is the completed PoGenerateResponse, not
      // a DesignReport — PoCard renders it straight into the success state (see PoCard.tsx).
      return <PoCard result={card.data as PoGenerateResponse} />;
    case "project_summary":
      return <ProjectSummaryCard project={card.data as Project | ProjectDetail} />;
    case "vendor_list":
      return <VendorListCard vendors={card.data as Vendor[]} />;
    case "rfq_status":
      return <RfqStatusCard data={card.data} />;
    case "component_pick":
      return <ComponentPickCard data={card.data} />;
    default:
      return null;
  }
}
