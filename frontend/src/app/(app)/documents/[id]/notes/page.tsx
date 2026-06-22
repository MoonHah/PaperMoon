"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Sparkles } from "lucide-react";
import { ApiError, generateDocumentNotes } from "@/lib/api";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";

// 笔记 tab：调专用接口按 document_id 精确生成（不走 Agent，避免指代歧义）。
// 生成结果按 docId 存入 sessionStorage：切到「阅读」再切回来不丢、刷新也在
// （后端暂不落盘以避开重建镜像；服务端持久化留到攻核心解析时一并做）。
export default function NotesTab() {
  const { id } = useParams<{ id: string }>();
  const storageKey = `papermoon:notes:${id}`;
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 挂载后从 sessionStorage 恢复（放 effect 里避免 SSR 水合不一致）。
  useEffect(() => {
    const cached = sessionStorage.getItem(storageKey);
    if (cached) setNote(cached);
    else setNote(null);
  }, [storageKey]);

  async function generate() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await generateDocumentNotes(id);
      setNote(res.notes);
      sessionStorage.setItem(storageKey, res.notes);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Button type="button" onClick={generate} loading={busy}>
        {!busy && <Sparkles className="h-4 w-4" aria-hidden />}
        {busy ? "生成中…" : note ? "重新生成" : "生成学习笔记"}
      </Button>

      {error && <p className="mt-3 text-danger">{error}</p>}

      {note && (
        <article className="mt-4 rounded-sm bg-canvas-read p-8 text-read-body text-ink-read">
          <Markdown>{note}</Markdown>
        </article>
      )}
    </div>
  );
}
