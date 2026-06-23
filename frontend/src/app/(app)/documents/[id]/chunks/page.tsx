"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, getDocumentChunks } from "@/lib/api";
import type { DocumentChunk } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

// 分块 tab：列出与入库一致的 chunk 切分（序号 + 字符数 + 内容），用于核查切分质量。
export default function ChunksTab() {
  const { id } = useParams<{ id: string }>();
  const [chunks, setChunks] = useState<DocumentChunk[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDocumentChunks(id)
      .then((r) => {
        if (!cancelled) setChunks(r.chunks);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <p className="text-destructive">{error}</p>;
  if (chunks === null)
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-sm" />
        ))}
      </div>
    );
  if (chunks.length === 0)
    return <p className="text-muted-foreground">该文档没有分块。</p>;

  return (
    <div>
      <p className="mb-4 text-sm text-muted-foreground">
        共 {chunks.length} 个分块 · 与向量库入库切分一致，每块独立参与检索。
      </p>
      <div className="space-y-3">
        {chunks.map((c) => (
          <div key={c.index} className="rounded-sm border border-border bg-card p-4">
            <div className="mb-2 flex items-center justify-between font-mono text-caption-mono-sm uppercase text-muted-foreground">
              <span>#{c.index}</span>
              <span>{c.char_count} 字符</span>
            </div>
            <p className="whitespace-pre-wrap break-words text-sm text-foreground">{c.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
