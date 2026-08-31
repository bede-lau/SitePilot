/**
 * Consumer for `POST /api/chat/stream` (ARD §5.5). Built on `fetch` + `ReadableStream` rather
 * than `EventSource`, which can only issue GET requests and can't carry the chat body/session.
 */
import { API_BASE } from "./api";
import type {
  CardEventPayload,
  ChatSendRequest,
  ChatStreamEvent,
  DeltaEventPayload,
  DoneEventPayload,
  ErrorEventPayload,
  StatusEventPayload,
  ToolEventPayload,
  ToolResultEventPayload,
  WarningEventPayload,
} from "./types";

export interface ChatStreamHandlers {
  onStatus?: (payload: StatusEventPayload) => void;
  onTool?: (payload: ToolEventPayload) => void;
  onToolResult?: (payload: ToolResultEventPayload) => void;
  onDelta?: (payload: DeltaEventPayload) => void;
  onCard?: (payload: CardEventPayload) => void;
  onWarning?: (payload: WarningEventPayload) => void;
  onDone?: (payload: DoneEventPayload) => void;
  onError?: (payload: ErrorEventPayload) => void;
  /** Fires for every parsed event, before the type-specific handler above. Handy for a debug trace. */
  onEvent?: (event: ChatStreamEvent) => void;
}

export interface ChatStreamHandle {
  /** Aborts the underlying fetch. Safe to call after the stream has already finished. */
  abort: () => void;
  /** Resolves once the stream has ended (successfully, on error, or aborted). */
  done: Promise<void>;
}

/** Splits a raw SSE frame into its `data:` payload, joining multi-line data as SSE requires. */
function extractData(frame: string): string | null {
  const dataLines = frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).replace(/^ /, ""));
  if (dataLines.length === 0) return null; // comment-only frame (heartbeat) or blank
  return dataLines.join("\n");
}

function dispatch(event: ChatStreamEvent, handlers: ChatStreamHandlers): void {
  handlers.onEvent?.(event);
  // Events are flat: the payload fields live directly on `event`, not under `event.data`.
  switch (event.type) {
    case "status":
      handlers.onStatus?.(event);
      break;
    case "tool":
      handlers.onTool?.(event);
      break;
    case "tool_result":
      handlers.onToolResult?.(event);
      break;
    case "delta":
      handlers.onDelta?.(event);
      break;
    case "card":
      handlers.onCard?.(event);
      break;
    case "warning":
      handlers.onWarning?.(event);
      break;
    case "done":
      handlers.onDone?.(event);
      break;
    case "error":
      handlers.onError?.(event);
      break;
  }
}

export function streamChat(request: ChatSendRequest, handlers: ChatStreamHandlers = {}): ChatStreamHandle {
  const controller = new AbortController();

  const done = (async () => {
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      handlers.onError?.({ message: err instanceof Error ? err.message : "Network error" });
      return;
    }

    if (!res.ok || !res.body) {
      handlers.onError?.({ message: `Stream request failed (${res.status})` });
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const drainFrames = (final: boolean) => {
      // sse-starlette emits CRLF line endings, so frames are separated by `\r\n\r\n`,
      // not `\n\n`. Normalising CRLF -> LF up front lets the split below work and
      // keeps `extractData` from seeing trailing `\r` on every `data:` line.
      // (Without this the split never matched, no event was ever dispatched, and the
      // UI sat on "Thinking…" forever even though the server had already streamed and
      // saved the reply — visible only after a reload.)
      buffer = buffer.replace(/\r\n/g, "\n");

      let sepIndex: number;
      while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        emitFrame(frame);
      }
      // On stream end a last frame may have no trailing blank line — flush it.
      if (final && buffer.trim()) {
        emitFrame(buffer);
        buffer = "";
      }
    };

    const emitFrame = (frame: string) => {
      const payload = extractData(frame);
      if (!payload) return; // heartbeat `:` comment or blank
      try {
        dispatch(JSON.parse(payload) as ChatStreamEvent, handlers);
      } catch {
        // Malformed frame — skip rather than kill the whole stream over one bad event.
      }
    };

    try {
      for (;;) {
        const { value, done: streamDone } = await reader.read();
        if (streamDone) {
          buffer += decoder.decode();
          drainFrames(true);
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        drainFrames(false);
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        handlers.onError?.({ message: err instanceof Error ? err.message : "Stream interrupted" });
      }
    }
  })();

  return { abort: () => controller.abort(), done };
}
