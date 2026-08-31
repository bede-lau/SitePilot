import { ArrowUp, Paperclip, Square, X } from "lucide-react";
import type { KeyboardEvent, ClipboardEvent } from "react";
import { useEffect, useRef } from "react";
import { cn } from "../../lib/cn";
import { IconButton } from "../ui";
import { MicButton } from "./MicButton";
import type { PendingAttachment } from "../../hooks/useAttachmentUploads";

const ACCEPT = ".pdf,application/pdf,image/*,.png,.jpg,.jpeg,.webp";

function kindTag(kind: string | undefined): string {
  if (kind === "pdf") return "PDF";
  if (kind === "audio") return "AUD";
  return "IMG";
}

export interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  streaming?: boolean;
  attachments: PendingAttachment[];
  onAddFiles: (files: File[]) => void;
  onRemoveAttachment: (id: string) => void;
  onTranscribed: (text: string) => void;
  onTextareaRef?: (el: HTMLTextAreaElement | null) => void;
  placeholder?: string;
}

/** Multiline autosize composer — ⌘Enter/Ctrl+Enter to send, paste-to-upload, attachment pills, and
 * disabled state while a reply is streaming. File selection and the mic both funnel into the same
 * `onAddFiles` / `onTranscribed` callbacks the panel wires to the upload + voice pipelines. */
export function Composer({
  value,
  onChange,
  onSend,
  onStop,
  streaming = false,
  attachments,
  onAddFiles,
  onRemoveAttachment,
  onTranscribed,
  onTextareaRef,
  placeholder = "Message Fieldbot…",
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(128, Math.max(36, el.scrollHeight))}px`;
  }, [value]);

  const canSend = !streaming && (value.trim().length > 0 || attachments.some((a) => a.status === "done"));

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      if (canSend) onSend();
    }
  }

  function onPaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    const files = Array.from(e.clipboardData.files ?? []);
    if (files.length) {
      e.preventDefault();
      onAddFiles(files);
    }
  }

  return (
    <div className="shrink-0 border-t border-border bg-bg-elevated p-3">
      {attachments.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {attachments.map((a) => (
            <span
              key={a.id}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border py-1 pl-2.5 pr-1.5 text-xs",
                a.status === "error" ? "border-danger/30 bg-danger/10 text-danger" : "border-border bg-bg-subtle text-muted",
              )}
            >
              {a.status === "uploading" ? (
                <span className="size-2.5 shrink-0 animate-pulse rounded-full bg-accent" aria-hidden="true" />
              ) : (
                <span className="shrink-0 rounded bg-accent/15 px-1 py-px text-[9px] font-semibold uppercase text-accent">{kindTag(a.result?.kind)}</span>
              )}
              <span className="max-w-[140px] truncate">{a.file.name}</span>
              <button
                type="button"
                onClick={() => onRemoveAttachment(a.id)}
                aria-label={`Remove ${a.file.name}`}
                className="rounded-full p-0.5 text-subtle hover:bg-surface-hover hover:text-text"
              >
                <X className="size-3" aria-hidden="true" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-end gap-1.5">
        <IconButton icon={<Paperclip />} aria-label="Attach a file" className="shrink-0" onClick={() => fileInputRef.current?.click()} disabled={streaming} />
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) onAddFiles(files);
            e.target.value = "";
          }}
        />

        <textarea
          ref={(el) => {
            textareaRef.current = el;
            onTextareaRef?.(el);
          }}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          rows={1}
          placeholder={placeholder}
          disabled={streaming}
          aria-label="Message"
          className="block h-9 max-h-32 min-h-9 w-full flex-1 resize-none overflow-y-auto bg-transparent py-2 text-sm leading-5 text-text placeholder:text-subtle focus:outline-none disabled:opacity-60"
        />

        <MicButton onTranscribed={onTranscribed} disabled={streaming} />

        {streaming ? (
          <IconButton icon={<Square className="fill-current" />} aria-label="Stop generating" variant="secondary" onClick={onStop} />
        ) : (
          <IconButton
            icon={<ArrowUp />}
            aria-label="Send message"
            variant="ghost"
            disabled={!canSend}
            onClick={onSend}
            className={canSend ? "bg-accent text-accent-fg hover:bg-accent-hover" : undefined}
          />
        )}
      </div>
      <p className="mt-1.5 pl-1 text-[10px] text-subtle">⌘Enter / Ctrl+Enter to send</p>
    </div>
  );
}
