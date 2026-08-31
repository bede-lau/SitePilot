import { Copy } from "lucide-react";
import { Badge, Button, Card, CardBody, CardHeader, useToast } from "../ui";
import type { BosSpec } from "../../lib/types";

function toMarkdown(bos: BosSpec): string {
  return bos.groups
    .map((g) => `### ${g.group}\n` + g.items.map((it) => `- **${it.item}** — ${it.spec} (${it.rating}) — ${it.standard}${it.note ? ` — ${it.note}` : ""}`).join("\n"))
    .join("\n\n");
}

/** Grouped balance-of-system checklist (fuses, isolators, cables, SPDs, earthing) with IEC/TNB
 * references, and a copy-as-markdown affordance for handoff to an installer. */
export function BosSpecCard({ bos }: { bos: BosSpec }) {
  const { toast } = useToast();

  async function copyMarkdown() {
    try {
      await navigator.clipboard.writeText(toMarkdown(bos));
      toast({ title: "Copied to clipboard", variant: "success", duration: 2500 });
    } catch {
      toast({ title: "Couldn't copy", description: "Clipboard access was blocked.", variant: "danger" });
    }
  }

  return (
    <Card elevation="sm">
      <CardHeader>
        <p className="text-sm font-semibold text-text">Balance-of-system spec</p>
        <Button size="sm" variant="secondary" iconLeft={<Copy className="size-3.5" />} onClick={copyMarkdown}>
          Copy
        </Button>
      </CardHeader>
      <CardBody className="space-y-4">
        {bos.groups.map((group) => (
          <div key={group.group}>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-subtle">{group.group}</p>
            <ul className="space-y-1.5">
              {group.items.map((item, i) => (
                <li key={i} className="rounded-lg border border-border bg-bg-subtle/50 px-3 py-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-text">{item.item}</span>
                    <Badge variant="neutral">{item.rating}</Badge>
                  </div>
                  <p className="mt-0.5 text-muted">{item.spec}</p>
                  <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-subtle">
                    <span>{item.standard}</span>
                    {item.note && <span className="truncate text-right">{item.note}</span>}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}
