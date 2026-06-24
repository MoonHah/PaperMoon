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
// 与"推理轨迹"同款折叠样式，避免大段原始 chunk 占据视线。
export function CitationCards({ citations }: { citations: CitedChunk[] }) {
  if (citations.length === 0) return null;

  return (
    <details className="mt-3 rounded-sm border border-border bg-muted">
      <summary className="cursor-pointer select-none px-4 py-2 font-mono text-caption-mono-sm uppercase text-muted-foreground">
        引用 · {citations.length}
      </summary>
      <div className="space-y-2 border-t border-border p-3">
        {citations.map((c, i) => (
          <div
            key={`${c.document_id}-${i}`}
            className="rounded-sm border-l-2 border-primary bg-card px-3 py-2"
          >
            <p className="line-clamp-2 text-sm text-foreground">{preview(c.text)}</p>
            <p className="mt-1 font-mono text-caption-mono-sm uppercase text-muted-foreground">
              {c.filename}
            </p>
          </div>
        ))}
      </div>
    </details>
  );
}
