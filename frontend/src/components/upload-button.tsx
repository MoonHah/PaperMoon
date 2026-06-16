"use client";

import { useRef, useState } from "react";
import { ApiError, uploadDocument } from "@/lib/api";
import type { DocumentUploadResponse } from "@/lib/types";

const ACCEPT = ".pdf,.md,.txt";

export function UploadButton({
  onUploaded,
}: {
  onUploaded: (doc: DocumentUploadResponse) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // 清空以允许重复选择同一文件
    if (!file) return;

    setBusy(true);
    setError(null);
    try {
      const doc = await uploadDocument(file);
      onUploaded(doc);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={handleChange}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="rounded-pill bg-ink px-4 py-1.5 text-sm font-medium text-canvas transition-colors hover:bg-ink/90 disabled:opacity-50"
      >
        {busy ? "上传中…" : "上传文档"}
      </button>
      {error ? (
        <span className="text-sm text-danger">{error}</span>
      ) : (
        <span className="text-xs text-mute">支持 .pdf / .md / .txt</span>
      )}
    </div>
  );
}
