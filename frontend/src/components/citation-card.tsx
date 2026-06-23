import type { CitedChunk } from "@/lib/types";

// 检索引用片段卡：左侧 sunset accent 竖线 + 片段正文 + 文件名脚注。
export function CitationCards({ citations }: { citations: CitedChunk[] }) {
  if (citations.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      <p className="font-mono text-caption-mono-sm uppercase text-muted-foreground">
        引用 · {citations.length}
      </p>
      {citations.map((c, i) => (
        <div
          key={`${c.document_id}-${i}`}
          className="rounded-sm border-l-2 border-primary bg-card p-4"
        >
          <p className="line-clamp-4 text-sm text-foreground">{c.text}</p>
          <p className="mt-2 font-mono text-caption-mono-sm uppercase text-muted-foreground">
            {c.filename}
          </p>
        </div>
      ))}
    </div>
  );
}
