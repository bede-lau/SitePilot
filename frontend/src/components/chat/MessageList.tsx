import { AlertTriangle, ArrowDown, Info, RotateCcw, Sparkles } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { cn } from "../../lib/cn";
import { formatRelativeTime } from "../../lib/format";
import { Button, SkeletonChatMessage } from "../ui";
import { CardRenderer } from "../cards";
import { LoadingState } from "./LoadingState";
import { Markdown } from "./Markdown";
import { StreamingText } from "./StreamingText";
import { ToolTrace } from "./ToolTrace";
import { useAutoScroll } from "../../hooks/useAutoScroll";
import type { LocalMessage } from "../../hooks/useChatSession";

export interface MessageListProps {
  messages: LocalMessage[];
  loading: boolean;
  onRetry: () => void;
}

function AttachmentPill({ filename }: { filename: string }) {
  return (
    <span className="inline-flex max-w-[180px] items-center gap-1 truncate rounded-full border border-accent-fg/25 bg-black/10 px-2 py-0.5 text-[11px] text-inherit">
      {filename}
    </span>
  );
}

export function MessageList({ messages, loading, onRetry }: MessageListProps) {
  const last = messages[messages.length - 1];
  const { ref, onScroll, stick, scrollToBottom } = useAutoScroll<HTMLDivElement>([
    messages.length,
    last?.content.length ?? 0,
    last?.cards.length ?? 0,
    last?.toolTrace.length ?? 0,
  ]);
  const reduceMotion = useReducedMotion();

  return (
    <div className="relative min-h-0 flex-1">
      <div ref={ref} onScroll={onScroll} className="flex h-full flex-col gap-4 overflow-y-auto px-4 py-4">
        {loading && (
          <div className="flex flex-col gap-4">
            <SkeletonChatMessage align="end" />
            <SkeletonChatMessage align="start" />
          </div>
        )}

        {!loading && messages.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 py-10 text-center">
            <div className="flex size-11 items-center justify-center rounded-full bg-accent/12 text-accent">
              <Sparkles className="size-5" aria-hidden="true" />
            </div>
            <p className="text-sm font-medium text-text">Ask Fieldbot anything</p>
            <p className="max-w-[240px] text-xs text-muted">Parse a quote, check feasibility, or ask about any project — try a suggestion below.</p>
          </div>
        )}

        {messages.map((message) => {
          const isUser = message.role === "user";
          return (
            <motion.div
              key={message.id}
              initial={reduceMotion ? undefined : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className={cn("flex flex-col gap-1.5", isUser ? "items-end" : "items-start")}
            >
              {!isUser && message.toolTrace.length > 0 && <div className="w-full max-w-[92%]">
                <ToolTrace entries={message.toolTrace} />
              </div>}

              {!isUser && message.streaming && !message.content && message.toolTrace.length === 0 && (
                <LoadingState label={message.statusLabel} />
              )}

              {message.content && (
                <div
                  className={cn(
                    "max-w-[92%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed",
                    isUser ? "bg-accent text-accent-fg" : "bg-bg-subtle text-text",
                  )}
                >
                  {isUser ? (
                    <span className="whitespace-pre-wrap break-words">{message.content}</span>
                  ) : message.streaming ? (
                    <StreamingText text={message.content} streaming className="whitespace-pre-wrap break-words" />
                  ) : (
                    <Markdown text={message.content} />
                  )}
                  {!isUser && message.statusLabel && (
                    <p className="mt-1.5 flex items-center gap-1.5 text-xs text-subtle">
                      <span className="size-1.5 animate-pulse rounded-full bg-accent" aria-hidden="true" />
                      {message.statusLabel}
                    </p>
                  )}
                </div>
              )}

              {isUser && message.attachments.length > 0 && (
                <div className="flex max-w-[92%] flex-wrap justify-end gap-1.5">
                  {message.attachments.map((a) => (
                    <AttachmentPill key={a.file_id} filename={a.filename} />
                  ))}
                </div>
              )}

              {message.warnings.map((w) => (
                <div
                  key={w.key}
                  className={cn(
                    "flex max-w-[92%] items-start gap-2 rounded-lg border px-3 py-2 text-xs",
                    w.level === "error"
                      ? "border-danger/30 bg-danger/10 text-danger"
                      : w.level === "warn"
                        ? "border-warning/30 bg-warning/10 text-warning"
                        : "border-info/30 bg-info/10 text-info",
                  )}
                >
                  {w.level === "info" ? <Info className="mt-px size-3.5 shrink-0" aria-hidden="true" /> : <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden="true" />}
                  <span>{w.message}</span>
                </div>
              ))}

              {message.cards.length > 0 && (
                <div className="flex w-full max-w-[92%] flex-col gap-3">
                  {message.cards.map((card, i) => (
                    <CardRenderer key={i} card={card} />
                  ))}
                </div>
              )}

              {message.errored && (
                <div className="flex items-center gap-2">
                  <p className="text-xs text-danger">Something went wrong.</p>
                  <Button size="sm" variant="secondary" iconLeft={<RotateCcw className="size-3.5" />} onClick={onRetry}>
                    Retry
                  </Button>
                </div>
              )}

              {!message.streaming && (
                <p className={cn("px-1 text-[10px] text-subtle", isUser && "text-right")}>{formatRelativeTime(message.createdAt)}</p>
              )}
            </motion.div>
          );
        })}
      </div>

      {!stick && messages.length > 0 && (
        <button
          type="button"
          onClick={scrollToBottom}
          className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-border bg-bg-elevated px-3 py-1.5 text-xs font-medium text-muted shadow-md transition-colors hover:text-text"
        >
          <ArrowDown className="size-3.5" aria-hidden="true" />
          New messages
        </button>
      )}
    </div>
  );
}
