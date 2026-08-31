import { Maximize2, Minimize2, PanelRightClose, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "../../lib/cn";
import { IconButton } from "../ui";
import { useAttachmentUploads } from "../../hooks/useAttachmentUploads";
import { useChatSession } from "../../hooks/useChatSession";
import { Composer } from "./Composer";
import { Dropzone } from "./Dropzone";
import { MessageList } from "./MessageList";
import { SuggestionChips } from "./SuggestionChips";

export interface ChatPanelProps {
  /** When set, renders a close affordance in the header — used by the mobile bottom-sheet host. */
  onRequestClose?: () => void;
  /** When set, renders a collapse affordance in the header — used by the docked desktop right rail. */
  onCollapse?: () => void;
  className?: string;
}

/** The chat workspace centrepiece: docked as a right rail at ≥1280px (see Layout), hosted inside a
 * bottom Sheet below that, and expandable to a full-screen overlay from either context. */
export function ChatPanel({ onRequestClose, onCollapse, className }: ChatPanelProps) {
  const { messages, send, retryLast, stop, isStreaming, historyLoaded, historyError } = useChatSession();
  const { items, addFiles, remove, clear, readyAttachments } = useAttachmentUploads();
  const [text, setText] = useState("");
  const [expanded, setExpanded] = useState(false);
  const textareaElRef = useRef<HTMLTextAreaElement | null>(null);

  // "/" focuses the composer from anywhere in the app (ARD §6.5 keyboard non-negotiable), unless
  // the user is already typing somewhere else.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "/") return;
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || target?.isContentEditable) return;
      e.preventDefault();
      textareaElRef.current?.focus();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!expanded) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setExpanded(false);
    }
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [expanded]);

  function handleSend() {
    const trimmed = text.trim();
    if (!trimmed && readyAttachments.length === 0) return;
    send(trimmed, readyAttachments);
    setText("");
    clear();
  }

  function handleSuggestion(prompt: string) {
    setText(prompt);
    textareaElRef.current?.focus();
  }

  const showSuggestions = historyLoaded && messages.length === 0;

  return (
    <Dropzone
      onFiles={addFiles}
      disabled={isStreaming}
      className={cn("flex flex-col", expanded ? "fixed inset-0 z-[60] bg-bg-elevated" : "h-full", className)}
    >
      <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
        <p className="flex-1 text-sm font-medium text-text">Fieldbot</p>
        <IconButton icon={expanded ? <Minimize2 /> : <Maximize2 />} aria-label={expanded ? "Exit full screen" : "Expand full screen"} size="sm" onClick={() => setExpanded((v) => !v)} />
        {onCollapse && !expanded && <IconButton icon={<PanelRightClose />} aria-label="Collapse panel" size="sm" onClick={onCollapse} />}
        {onRequestClose && <IconButton icon={<X />} aria-label="Close chat" size="sm" onClick={onRequestClose} />}
      </div>

      <MessageList messages={messages} loading={!historyLoaded} onRetry={retryLast} />

      {historyError && <p className="px-4 pb-1 text-[11px] text-subtle">Couldn't load earlier history — you can still send new messages.</p>}

      <div className="shrink-0">
        {showSuggestions && (
          <div className="px-4 pb-2">
            <SuggestionChips onSelect={handleSuggestion} disabled={isStreaming} />
          </div>
        )}
        <Composer
          value={text}
          onChange={setText}
          onSend={handleSend}
          onStop={stop}
          streaming={isStreaming}
          attachments={items}
          onAddFiles={addFiles}
          onRemoveAttachment={remove}
          onTranscribed={(t) => setText((prev) => (prev ? `${prev} ${t}` : t))}
          onTextareaRef={(el) => (textareaElRef.current = el)}
        />
      </div>
    </Dropzone>
  );
}
