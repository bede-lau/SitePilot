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
  switch (event.type) {
    case "status":
      handlers.onStatus?.(event.data);
      break;
    case "tool":
      handlers.onTool?.(event.data);
      break;
    case "tool_result":
      handlers.onToolResult?.(event.data);
      break;
    case "delta":
      handlers.onDelta?.(event.data);
      break;
    case "card":
      handlers.onCard?.(event.data);
      break;
    case "warning":
      handlers.onWarning?.(event.data);
      break;
    case "done":
      handlers.onDone?.(event.data);
      break;
    case "error":
      handlers.onError?.(event.data);
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

    try {
      for (;;) {
        const { value, done: streamDone } = await reader.read();
        if (streamDone) break;
        buffer += decoder.decode(value, { stream: true });

        let sepIndex: number;
        // SSE frames are separated by a blank line; a frame may carry several `data:` lines.
        while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, sepIndex);
          buffer = buffer.slice(sepIndex + 2);

          const payload = extractData(frame);
          if (!payload) continue; // heartbeat `:` comment

          try {
            dispatch(JSON.parse(payload) as ChatStreamEvent, handlers);
          } catch {
            // Malformed frame — skip rather than kill the whole stream over one bad event.
          }
        }
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        handlers.onError?.({ message: err instanceof Error ? err.message : "Stream interrupted" });
      }
    }
  })();

  return { abort: () => controller.abort(), done };
}
