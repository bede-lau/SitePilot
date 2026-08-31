import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { streamChat } from "../lib/sse";
import type {
  CardEventPayload,
  ChatCard,
  ChatMessage,
  ChatRole,
  ToolEventPayload,
  ToolResultEventPayload,
  UploadResponse,
  WarningEventPayload,
} from "../lib/types";

const SESSION_KEY_STORAGE = "sitepilot-chat-session";

export interface ToolTraceEntry {
  key: string;
  name: string;
  status: "running" | "ok" | "error";
  summary?: string;
  ms?: number;
}

export interface ChatWarning {
  key: string;
  level: WarningEventPayload["level"];
  message: string;
}

export interface LocalMessage {
  id: string;
  role: ChatRole;
  content: string;
  cards: ChatCard[];
  attachments: UploadResponse[];
  toolTrace: ToolTraceEntry[];
  warnings: ChatWarning[];
  statusLabel: string | null;
  streaming: boolean;
  errored: boolean;
  createdAt: string;
}

function getSessionKey(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY_STORAGE);
    if (existing) return existing;
    const next = `web:${crypto.randomUUID()}`;
    localStorage.setItem(SESSION_KEY_STORAGE, next);
    return next;
  } catch {
    return `web:${crypto.randomUUID()}`;
  }
}

function fromServerMessage(msg: ChatMessage): LocalMessage {
  return {
    id: String(msg.id),
    role: msg.role,
    content: msg.content,
    cards: msg.cards,
    attachments: msg.attachments,
    toolTrace: [],
    warnings: [],
    statusLabel: null,
    streaming: false,
    errored: false,
    createdAt: msg.created_at,
  };
}

/**
 * Drives the chat workspace against `POST /api/chat/stream` (ARD §5.5). Owns the message list,
 * per-message tool trace / warnings accumulated from SSE events, and a retry affordance that
 * re-sends the last user turn after dropping its failed assistant reply.
 */
export function useChatSession() {
  // A stable per-tab session key, never reassigned — plain state (read directly, not via a ref)
  // so it can be read during render without tripping the "no ref access during render" rule.
  const [sessionKey] = useState(getSessionKey);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<(() => void) | null>(null);
  const lastTurnRef = useRef<{ text: string; attachments: UploadResponse[] } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getChatHistory(sessionKey)
      .then((history) => {
        if (cancelled) return;
        setMessages(history.map(fromServerMessage));
        setHistoryLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setHistoryLoaded(true);
        setHistoryError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionKey]);

  const updateMessage = useCallback((id: string, updater: (msg: LocalMessage) => LocalMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)));
  }, []);

  const send = useCallback(
    (text: string, attachments: UploadResponse[] = []) => {
      const trimmed = text.trim();
      if (!trimmed && attachments.length === 0) return;

      lastTurnRef.current = { text: trimmed, attachments };

      const userMessage: LocalMessage = {
        id: `local-${crypto.randomUUID()}`,
        role: "user",
        content: trimmed,
        cards: [],
        attachments,
        toolTrace: [],
        warnings: [],
        statusLabel: null,
        streaming: false,
        errored: false,
        createdAt: new Date().toISOString(),
      };

      const assistantId = `local-${crypto.randomUUID()}`;
      const assistantMessage: LocalMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        cards: [],
        attachments: [],
        toolTrace: [],
        warnings: [],
        statusLabel: "Thinking…",
        streaming: true,
        errored: false,
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);

      const handle = streamChat(
        { session_key: sessionKey, message: trimmed, attachments },
        {
          onStatus: (payload) => {
            updateMessage(assistantId, (m) => ({ ...m, statusLabel: payload.label }));
          },
          onTool: (payload: ToolEventPayload) => {
            updateMessage(assistantId, (m) => ({
              ...m,
              statusLabel: null,
              toolTrace: [...m.toolTrace, { key: `${payload.name}-${m.toolTrace.length}`, name: payload.name, status: "running" }],
            }));
          },
          onToolResult: (payload: ToolResultEventPayload) => {
            updateMessage(assistantId, (m) => {
              const reverseIdx = [...m.toolTrace].reverse().findIndex((t) => t.name === payload.name && t.status === "running");
              if (reverseIdx === -1) return m;
              const idx = m.toolTrace.length - 1 - reverseIdx;
              const next = [...m.toolTrace];
              next[idx] = { ...next[idx], status: payload.ok ? "ok" : "error", summary: payload.summary, ms: payload.ms };
              return { ...m, toolTrace: next };
            });
          },
          onDelta: (payload) => {
            updateMessage(assistantId, (m) => ({ ...m, content: m.content + payload.text, statusLabel: null }));
          },
          onCard: (payload: CardEventPayload) => {
            updateMessage(assistantId, (m) => ({ ...m, cards: [...m.cards, { card_type: payload.card_type, data: payload.data }] }));
          },
          onWarning: (payload) => {
            updateMessage(assistantId, (m) => ({
              ...m,
              warnings: [...m.warnings, { key: crypto.randomUUID(), level: payload.level, message: payload.message }],
            }));
          },
          onDone: (payload) => {
            updateMessage(assistantId, (m) => ({
              ...m,
              id: String(payload.message_id),
              cards: payload.cards.length ? payload.cards : m.cards,
              streaming: false,
              statusLabel: null,
            }));
            setIsStreaming(false);
          },
          onError: (payload) => {
            updateMessage(assistantId, (m) => ({
              ...m,
              streaming: false,
              errored: true,
              statusLabel: null,
              content: m.content || payload.message,
            }));
            setIsStreaming(false);
          },
        },
      );

      abortRef.current = handle.abort;
      handle.done.finally(() => {
        abortRef.current = null;
      });
    },
    [sessionKey, updateMessage],
  );

  const retryLast = useCallback(() => {
    const last = lastTurnRef.current;
    if (!last) return;
    setMessages((prev) => {
      const trimmedList = [...prev];
      if (trimmedList.length && trimmedList[trimmedList.length - 1].errored) trimmedList.pop();
      if (trimmedList.length && trimmedList[trimmedList.length - 1].role === "user") trimmedList.pop();
      return trimmedList;
    });
    send(last.text, last.attachments);
  }, [send]);

  const stop = useCallback(() => {
    abortRef.current?.();
    setIsStreaming(false);
  }, []);

  return {
    messages,
    send,
    retryLast,
    stop,
    isStreaming,
    historyLoaded,
    historyError,
    sessionKey,
  };
}
