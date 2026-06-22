"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, getDocumentContent } from "@/lib/api";
import { Markdown } from "@/components/markdown";
import { Skeleton } from "@/components/ui/skeleton";

// 阅读 tab：reader-pane（软黑底 + 微灰白字护眼）。
export default function ReadTab() {
  const { id } = useParams<{ id: string }>();
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDocumentContent(id)
      .then((r) => {
        if (!cancelled) setContent(r.content);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <p className="text-danger">{error}</p>;
  if (content === null)
    return (
      <div className="space-y-3 rounded-sm bg-canvas-read p-8">
        <Skeleton className="h-6 w-1/2" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className={`h-4 ${i % 3 === 2 ? "w-2/3" : "w-full"}`} />
        ))}
      </div>
    );

  return (
    <article className="rounded-sm bg-canvas-read p-8 text-read-body text-ink-read motion-safe:animate-[fadeIn_200ms_ease-out]">
      <Markdown>{content}</Markdown>
    </article>
  );
}
