"use client";

import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Skeleton } from "@/components/ui/skeleton";

// 在应用内用 pdf.js 渲染 PDF（canvas），不依赖浏览器的 PDF 查看器设置。
// worker 自托管：用 new URL(import.meta.url) 让打包器解析并 emit 本地资源，不走 CDN（国内可用）。
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function PdfViewer({ file }: { file: Blob }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [numPages, setNumPages] = useState(0);
  const [failed, setFailed] = useState(false);

  // 跟随容器宽度自适应（每页按容器宽渲染）。
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => setWidth(el.clientWidth);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="flex flex-col items-center gap-4">
      {failed ? (
        <p className="text-sm text-destructive">PDF 渲染失败。</p>
      ) : (
        <Document
          file={file}
          onLoadSuccess={({ numPages }) => setNumPages(numPages)}
          onLoadError={() => setFailed(true)}
          loading={<Skeleton className="h-[70vh] w-full rounded-sm" />}
        >
          {Array.from({ length: numPages }, (_, i) => (
            <Page
              key={i}
              pageNumber={i + 1}
              width={width > 0 ? width : undefined}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              className="mb-4 overflow-hidden rounded-sm border border-border shadow-sm"
            />
          ))}
        </Document>
      )}
    </div>
  );
}
