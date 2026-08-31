import { useCallback, useState } from "react";
import { api } from "../lib/api";
import type { UploadResponse } from "../lib/types";

export type PendingAttachmentStatus = "uploading" | "done" | "error";

export interface PendingAttachment {
  id: string;
  file: File;
  status: PendingAttachmentStatus;
  result?: UploadResponse;
  errorMessage?: string;
}

/** Optimistic upload pipeline for the composer: a file appears as a pill immediately, uploads in
 * the background via `POST /api/uploads`, and resolves to the `UploadResponse` the chat send needs. */
export function useAttachmentUploads() {
  const [items, setItems] = useState<PendingAttachment[]>([]);

  const addFiles = useCallback((files: File[]) => {
    const next: PendingAttachment[] = files.map((file) => ({ id: crypto.randomUUID(), file, status: "uploading" }));
    setItems((prev) => [...prev, ...next]);

    next.forEach((item) => {
      api
        .uploadFile(item.file)
        .then((result) => {
          setItems((prev) => prev.map((p) => (p.id === item.id ? { ...p, status: "done", result } : p)));
        })
        .catch(() => {
          setItems((prev) => prev.map((p) => (p.id === item.id ? { ...p, status: "error", errorMessage: "Upload failed" } : p)));
        });
    });
  }, []);

  const remove = useCallback((id: string) => {
    setItems((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const readyAttachments = items.filter((i): i is PendingAttachment & { result: UploadResponse } => i.status === "done" && !!i.result).map((i) => i.result);
  const isUploading = items.some((i) => i.status === "uploading");

  return { items, addFiles, remove, clear, readyAttachments, isUploading };
}
