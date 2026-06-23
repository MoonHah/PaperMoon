"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, fetchDocumentFile, getDocument, getDocumentContent } from "@/lib/api";
import { Markdown } from "@/components/markdown";
import { PdfViewer } from "@/components/pdf-viewer";
import { Skeleton } from "@/components/ui/skeleton";

// 阅读 tab：展示「原件」。PDF 用 pdf.js 应用内渲染（不依赖浏览器 PDF 设置）；txt/md 渲染文本。
export default function ReadTab() {
  const { id } = useParams<{ id: string }>();
  const [fileType, setFileType] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setFileType(null);
    setPdfBlob(null);
    setContent(null);

    (async () => {
      try {
        const doc = await getDocument(id);
        if (cancelled) return;
        setFileType(doc.file_type);
        if (doc.file_type === ".pdf") {
          const blob = await fetchDocumentFile(id); // 带 Bearer 拉原件，交给 pdf.js 渲染
          if (!cancelled) setPdfBlob(blob);
        } else {
          const r = await getDocumentContent(id);
          if (!cancelled) setContent(r.content);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "加载失败");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <p className="text-destructive">{error}</p>;
  if (fileType === null) return <Skeleton className="h-[70vh] w-full rounded-sm" />;

  if (fileType === ".pdf") {
    if (!pdfBlob) return <Skeleton className="h-[70vh] w-full rounded-sm" />;
    return <PdfViewer file={pdfBlob} />;
  }

  // txt/md：原文即文本
  if (content === null)
    return (
      <div className="space-y-3 rounded-sm bg-card p-8">
        <Skeleton className="h-6 w-1/2" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className={`h-4 ${i % 3 === 2 ? "w-2/3" : "w-full"}`} />
        ))}
      </div>
    );

  return (
    <article className="rounded-sm bg-card p-8 text-read-body text-foreground motion-safe:animate-[fadeIn_200ms_ease-out]">
      <Markdown>{content}</Markdown>
    </article>
  );
}
