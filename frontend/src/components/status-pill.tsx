import type { DocStatus } from "@/lib/types";

const LABELS: Record<DocStatus, string> = {
  UPLOADED: "已上传",
  PARSING: "解析中",
  CHUNKING: "分块中",
  EMBEDDING: "向量化",
  INDEXING: "入库中",
  READY: "就绪",
  FAILED: "失败",
};

// 颜色由 semantic 决定：就绪→success，失败→danger，其余处理中→processing。
function styleFor(status: DocStatus): string {
  if (status === "READY") return "bg-success/10 text-success";
  if (status === "FAILED") return "bg-destructive/10 text-destructive";
  return "bg-info/10 text-info";
}

export function StatusPill({ status }: { status: DocStatus }) {
  const processing = status !== "READY" && status !== "FAILED";

  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-0.5 font-mono text-caption-mono-sm uppercase ${styleFor(status)}`}
    >
      {processing && (
        <span className="h-1.5 w-1.5 rounded-full bg-info motion-safe:animate-pulse" />
      )}
      {LABELS[status] ?? status}
    </span>
  );
}
