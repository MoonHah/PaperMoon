import Link from "next/link";
import { BookOpen } from "lucide-react";
import type { CitedChunk } from "@/lib/types";

// 把检索片段清洗成简短预览：去表格边框/分隔线(-----)、竖线、折叠空白再截断——
// 避免 PDF 解析残留的表格噪声污染观感。
function preview(text: string): string {
  const cleaned = text
    .replace(/[-–—_=]{3,}/g, " ") // 表格边框 / 水平分隔线
    .replace(/\|/g, " ") // 表格竖线
    .replace(/\s+/g, " ") // 折叠空白
    .trim();
  if (!cleaned) return "（表格或分隔片段）";
  return cleaned.length > 140 ? cleaned.slice(0, 140) + "…" : cleaned;
}

// 检索引用片段：默认折叠（点开看来源），每条显示清洗后的简短预览 + 文件名。
// 整条可点 → 跳到该文档的阅读页（缝合"对话 → 阅读原文"）。
export function CitationCards({ citations }: { citations: CitedChunk[] }) {
  if (citations.length === 0) return null;

  return (
    <details className="mt-3 rounded-sm border border-border bg-muted">
      <summary className="cursor-pointer select-none px-4 py-2 font-mono text-caption-mono-sm uppercase text-muted-foreground">
        引用 · {citations.length}
      </summary>
      <div className="space-y-2 border-t border-border p-3">
        {citations.map((c, i) => (
          <Link
            key={`${c.document_id}-${i}`}
            href={`/documents/${c.document_id}/read`}
            className="group block rounded-sm border-l-2 border-primary bg-card px-3 py-2 transition-colors hover:bg-accent"
          >
            <p className="line-clamp-2 text-sm text-foreground">{preview(c.text)}</p>
            <p className="mt-1 flex items-center gap-1 font-mono text-caption-mono-sm uppercase text-muted-foreground">
              <BookOpen className="h-3 w-3 shrink-0" aria-hidden />
              <span className="truncate">{c.filename}</span>
              <span className="ml-auto shrink-0 normal-case opacity-0 transition-opacity group-hover:opacity-100">
                打开原文
              </span>
            </p>
          </Link>
        ))}
      </div>
    </details>
  );
}
