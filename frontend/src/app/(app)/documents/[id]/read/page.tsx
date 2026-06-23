"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError, fetchDocumentFile, getDocument, getDocumentContent } from "@/lib/api";
import { Markdown } from "@/components/markdown";
import { Skeleton } from "@/components/ui/skeleton";

// 阅读 tab：展示「原件」。PDF 内嵌渲染原始文件（保留版式/图/公式）；txt/md 渲染文本。
// 解析正文与分块见「分块」tab。
export default function ReadTab() {
  const { id } = useParams<{ id: string }>();
  const [fileType, setFileType] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setError(null);
    setFileType(null);
    setPdfUrl(null);
    setContent(null);

    (async () => {
      try {
        const doc = await getDocument(id);
        if (cancelled) return;
        setFileType(doc.file_type);
        if (doc.file_type === ".pdf") {
          // <iframe src> 带不了 Bearer → 鉴权 fetch 成 blob 再生成 object URL 内嵌。
          const blob = await fetchDocumentFile(id);
          if (cancelled) return;
          // 强制 MIME 为 application/pdf：防代理未透传 Content-Type 时浏览器当未知类型下载。
          const pdfBlob =
            blob.type === "application/pdf"
              ? blob
              : new Blob([blob], { type: "application/pdf" });
          objectUrl = URL.createObjectURL(pdfBlob);
          setPdfUrl(objectUrl);
        } else {
          const r = await getDocumentContent(id);
          if (cancelled) return;
          setContent(r.content);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "加载失败");
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl); // 释放 blob，防内存泄漏
    };
  }, [id]);

  if (error) return <p className="text-destructive">{error}</p>;
  if (fileType === null) return <Skeleton className="h-[70vh] w-full rounded-sm" />;

  if (fileType === ".pdf") {
    if (!pdfUrl) return <Skeleton className="h-[70vh] w-full rounded-sm" />;
    // <object type="application/pdf"> 显式声明类型，比 <iframe> 更稳地内联渲染 blob PDF；
    // 内部子节点为兜底（浏览器无法内嵌时显示下载链接）。
    return (
      <object
        data={pdfUrl}
        type="application/pdf"
        className="h-[calc(100vh-220px)] min-h-[600px] w-full rounded-sm border border-border bg-card"
      >
        <div className="p-8 text-center text-sm text-muted-foreground">
          浏览器无法内嵌显示此 PDF。
          <a href={pdfUrl} download className="ml-1 text-primary underline">
            下载查看
          </a>
        </div>
      </object>
    );
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
