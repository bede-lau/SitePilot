import { FileUp, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { QuoteCard } from "../components/cards";
import { Dropzone } from "../components/chat";
import { Badge, Card, CardBody, CardHeader, EmptyState, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui";
import { api } from "../lib/api";
import { formatMYR, formatNumber } from "../lib/format";
import type { SupplierQuote } from "../lib/types";

/** Quote inbox (ARD §6.3): whole-panel dropzone → `POST /api/uploads` → `POST /api/quotes/parse`,
 * an RM/Wp comparison table across every parsed quote, and an RFQ batch tracker placeholder — the
 * API has no list endpoint for RFQ batches yet, so that panel points to chat instead of guessing. */
export default function Procurement() {
  const [quotes, setQuotes] = useState<SupplierQuote[]>([]);
  const [loading, setLoading] = useState(true);
  const [parsing, setParsing] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .listQuotes()
      .then((q) => {
        setQuotes(q);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  async function handleFiles(files: File[]) {
    setUploadError(null);
    for (const file of files) {
      setParsing((prev) => [...prev, file.name]);
      try {
        const uploaded = await api.uploadFile(file);
        const quote = await api.parseQuote(uploaded.file_id);
        setQuotes((prev) => [quote, ...prev]);
        setSelectedId(quote.id);
      } catch {
        setUploadError(`Couldn't process "${file.name}". Make sure the backend is running and the file is a PDF or image.`);
      } finally {
        setParsing((prev) => prev.filter((n) => n !== file.name));
      }
    }
  }

  const selected = quotes.find((q) => q.id === selectedId) ?? quotes[0] ?? null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-text">Procurement</h1>
        <p className="mt-1 text-sm text-muted">Drop a supplier quote to extract line items, normalize RM/Wp, and check BNEF tier status.</p>
      </div>

      <Dropzone onFiles={handleFiles} className="rounded-xl">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="flex w-full flex-col items-center rounded-xl border-2 border-dashed border-border bg-bg-subtle/40 p-8 text-center transition-colors duration-[120ms] hover:border-accent/60 hover:bg-bg-subtle/70 focus-visible:border-accent/60"
        >
          <FileUp className="size-6 text-subtle" aria-hidden="true" />
          <span className="mt-2 text-sm font-medium text-text">Drag a quote here, or click to browse</span>
          <span className="mt-1 text-xs text-muted">PDF or image — messy multi-currency supplier quotes welcome</span>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf,image/*,.png,.jpg,.jpeg,.webp"
          multiple
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) handleFiles(files);
            e.target.value = "";
          }}
        />
      </Dropzone>

      {uploadError && (
        <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">{uploadError}</p>
      )}

      {parsing.length > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-bg-subtle px-3 py-2 text-xs text-muted">
          <Loader2 className="size-3.5 animate-spin text-accent" aria-hidden="true" />
          Parsing {parsing.join(", ")}…
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_420px]">
        <Card elevation="sm">
          <CardHeader>
            <p className="text-sm font-semibold text-text">RM/Wp comparison</p>
            <span className="text-xs text-muted">{quotes.length} quotes</span>
          </CardHeader>
          <CardBody className="p-0">
            {loading ? (
              <div className="p-6 text-sm text-muted">Loading…</div>
            ) : quotes.length === 0 ? (
              <EmptyState title="No quotes yet" body="Parsed supplier quotes will appear here, ready to compare." />
            ) : (
              <Table>
                <TableHead>
                  <tr>
                    <TableHeaderCell>Supplier</TableHeaderCell>
                    <TableHeaderCell>RM/Wp</TableHeaderCell>
                    <TableHeaderCell>Total Wp</TableHeaderCell>
                    <TableHeaderCell>Subtotal</TableHeaderCell>
                    <TableHeaderCell>Status</TableHeaderCell>
                  </tr>
                </TableHead>
                <TableBody>
                  {quotes.map((q) => (
                    <TableRow key={q.id} onClick={() => setSelectedId(q.id)} className="cursor-pointer">
                      <TableCell className="font-medium text-text">{q.supplier_name_raw}</TableCell>
                      <TableCell className="tabular-nums">{q.summary.blended_price_per_wp_myr != null ? `RM ${q.summary.blended_price_per_wp_myr.toFixed(3)}` : "—"}</TableCell>
                      <TableCell className="tabular-nums">{formatNumber(q.summary.total_wp)}</TableCell>
                      <TableCell className="tabular-nums">{formatMYR(q.subtotal_myr)}</TableCell>
                      <TableCell>
                        <Badge variant={q.parse_status === "parsed" ? "success" : q.parse_status === "partial" ? "warning" : "danger"}>{q.parse_status}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardBody>
        </Card>

        <div className="space-y-4">
          {selected ? <QuoteCard quote={selected} /> : <EmptyState title="Select a quote" body="Pick a row from the comparison table to see its full line-item breakdown." />}

          <Card elevation="sm">
            <CardHeader>
              <p className="text-sm font-semibold text-text">RFQ batch tracker</p>
            </CardHeader>
            <CardBody>
              <EmptyState title="Start an RFQ from chat" body='Ask Fieldbot to "start procurement" for an item and region — batches will track vendor replies here.' />
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
