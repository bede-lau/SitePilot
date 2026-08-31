import { Fragment, type ReactNode } from "react";
import { cn } from "../../lib/cn";

/**
 * Tiny Markdown renderer for assistant replies — covers the subset Fieldbot emits:
 * `**bold**`, `*italic*` / `_italic_`, `` `code` ``, `#`–`###` headings, `-`/`*` bullet lists,
 * `1.` ordered lists, `>` blockquotes, `---` rules, and blank-line-separated paragraphs.
 * Builds React nodes directly (no `dangerouslySetInnerHTML`), so input is never treated as HTML.
 */

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  // Split on the inline tokens while keeping the delimiters.
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|(?<![*\w])\*[^*\n]+\*(?!\w)|(?<![_\w])_[^_\n]+_(?!\w))/g);
  return parts.filter(Boolean).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={key} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={key} className="rounded bg-black/10 px-1 py-0.5 font-mono text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (
      (part.startsWith("*") && part.endsWith("*") && part.length > 2) ||
      (part.startsWith("_") && part.endsWith("_") && part.length > 2)
    ) {
      return (
        <em key={key} className="italic">
          {part.slice(1, -1)}
        </em>
      );
    }
    return <Fragment key={key}>{part}</Fragment>;
  });
}

type Block =
  | { kind: "heading"; level: number; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "hr" }
  | { kind: "p"; text: string };

function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let para: string[] = [];

  const flushPara = () => {
    if (para.length) {
      blocks.push({ kind: "p", text: para.join(" ") });
      para = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      flushPara();
      continue;
    }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushPara();
      blocks.push({ kind: "hr" });
      continue;
    }
    const heading = trimmed.match(/^(#{1,3})\s+(.*)$/);
    if (heading) {
      flushPara();
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2] });
      continue;
    }
    if (/^[-*]\s+/.test(trimmed)) {
      flushPara();
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      i--;
      blocks.push({ kind: "ul", items });
      continue;
    }
    if (/^\d+[.)]\s+/.test(trimmed)) {
      flushPara();
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+[.)]\s+/, ""));
        i++;
      }
      i--;
      blocks.push({ kind: "ol", items });
      continue;
    }
    if (/^>\s?/.test(trimmed)) {
      flushPara();
      blocks.push({ kind: "quote", text: trimmed.replace(/^>\s?/, "") });
      continue;
    }
    para.push(trimmed);
  }
  flushPara();
  return blocks;
}

const HEADING_CLASS: Record<number, string> = {
  1: "text-base font-semibold",
  2: "text-sm font-semibold",
  3: "text-sm font-semibold text-muted",
};

export function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = parseBlocks(text);
  return (
    <div className={cn("flex flex-col gap-2 break-words", className)}>
      {blocks.map((block, bi) => {
        switch (block.kind) {
          case "heading": {
            const Tag = (`h${block.level}` as "h1" | "h2" | "h3");
            return (
              <Tag key={bi} className={HEADING_CLASS[block.level]}>
                {renderInline(block.text, `h${bi}`)}
              </Tag>
            );
          }
          case "ul":
            return (
              <ul key={bi} className="flex flex-col gap-1 pl-4">
                {block.items.map((it, ii) => (
                  <li key={ii} className="list-disc marker:text-subtle">
                    {renderInline(it, `ul${bi}-${ii}`)}
                  </li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={bi} className="flex flex-col gap-1 pl-4">
                {block.items.map((it, ii) => (
                  <li key={ii} className="list-decimal marker:text-subtle">
                    {renderInline(it, `ol${bi}-${ii}`)}
                  </li>
                ))}
              </ol>
            );
          case "quote":
            return (
              <blockquote key={bi} className="border-l-2 border-border pl-3 text-muted">
                {renderInline(block.text, `q${bi}`)}
              </blockquote>
            );
          case "hr":
            return <hr key={bi} className="border-border" />;
          default:
            return (
              <p key={bi} className="leading-relaxed">
                {renderInline(block.text, `p${bi}`)}
              </p>
            );
        }
      })}
    </div>
  );
}
