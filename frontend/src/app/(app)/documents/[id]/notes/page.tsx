"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, generateDocumentNotes } from "@/lib/api";

// 笔记 tab：调专用接口按 document_id 精确生成（不走 Agent，避免指代歧义）。
export default function NotesTab() {
  const { id } = useParams<{ id: string }>();
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await generateDocumentNotes(id);
      setNote(res.notes);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={generate}
        disabled={busy}
        className="rounded-pill bg-ink px-4 py-1.5 text-sm font-medium text-canvas transition-colors hover:bg-ink/90 disabled:opacity-50"
      >
        {busy ? "生成中…" : note ? "重新生成" : "生成学习笔记"}
      </button>

      {error && <p className="mt-3 text-danger">{error}</p>}

      {note && (
        <article className="mt-4 rounded-sm bg-canvas-read p-8">
          <div className="whitespace-pre-wrap text-read-body text-ink-read">{note}</div>
        </article>
      )}
    </div>
  );
}
